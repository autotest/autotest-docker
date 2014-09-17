r"""
Summary
----------

This test checks function of `docker logs --follow`

Operational Summary
---------------------
1.  Start container
2.  Start `docker logs --follow` process
3.  Execute couple of cmds
4.  Start `docker logs` (without --follow) process
5.  Execute couple of cmds (output to stderr)
6.  Stop container
7.  Start `docker logs` (without --follow) process
8.  Check correctness o 2, then compare 2 and 7 (match) and 4 (partial
    match). Also check all exit statuses/errors/...
"""

import os
import time
from autotest.client import utils
from dockertest import config, xceptions
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd, AsyncDockerCmd
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtestCaller, SubSubtest
from dockertest.xceptions import DockerTestFail


class InteractiveAsyncDockerCmd(AsyncDockerCmd):

    """
    Execute docker command as asynchronous background process on ``execute()``
    with PIPE as stdin and allows use of stdin(data) to interact with process.
    """

    def __init__(self, subtest, subcmd, subargs=None, timeout=None,
                 verbose=True):
        super(InteractiveAsyncDockerCmd, self).__init__(subtest, subcmd,
                                                        subargs, timeout,
                                                        verbose)
        self._stdin = None
        self._stdout_idx = 0

    def execute(self, stdin=None):
        """
        Start execution of asynchronous docker command
        """
        ps_stdin, self._stdin = os.pipe()
        ret = super(InteractiveAsyncDockerCmd, self).execute(ps_stdin)
        os.close(ps_stdin)
        if stdin:
            for line in stdin.splitlines(True):
                self.stdin(line)
        return ret

    def stdin(self, data):
        """
        Sends data to stdin (partial send is possible!)
        :param data: Data to be send
        :return: Number of written data
        """
        return os.write(self._stdin, data)

    def close(self):
        """
        Close the pipes (when opened)
        """
        if self._stdin:
            os.close(self._stdin)
            self._stdin = None


class Output(object):   # only containment pylint: disable=R0903

    """
    Wraps object with `.stdout` method and returns only new chars out of it
    """

    def __init__(self, stuff, idx=None):
        self.stuff = stuff
        if idx is None:
            self.idx = len(stuff.stdout.splitlines())
        else:
            self.idx = idx
        self.erridx = len(stuff.stderr.splitlines())

    def get(self, idx=None):
        """
        :param idx: Override last index
        :return: Output of stuff.stdout from idx (or last read)
        """
        if idx is None:
            idx = self.idx
        out = self.stuff.stdout.splitlines()
        self.idx = len(out)
        return out[idx:]

    def geterr(self, idx=None):
        """
        :param idx: Override last index
        :return: Output of stuff.stdout from idx (or last read)
        """
        if idx is None:
            idx = self.erridx
        out = self.stuff.stderr.splitlines()
        self.erridx = len(out)
        return out[idx:]


class logs_follow(SubSubtestCaller):

    """ Subtest caller """


class logs_follow_base(SubSubtest):

    """ Base class """

    def _init_container(self, subargs, cmd):
        """
        Prepares dkrcmd and stores the name in self.sub_stuff['containers']
        and command in self.sub_stuff['async_processes'].
        :return: tuple(dkrcmd, name)
        """
        name = self.sub_stuff['dc'].get_unique_name()
        subargs.append("--name %s" % name)
        self.sub_stuff['containers'].append(name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append(cmd)
        dkrcmd = InteractiveAsyncDockerCmd(self, 'run', subargs, verbose=False)
        self.sub_stuff['async_processes'].append(dkrcmd)
        return dkrcmd, name

    def initialize(self):
        super(logs_follow_base, self).initialize()
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['containers'] = []
        self.sub_stuff['async_processes'] = []

    def _cleanup_containers(self):
        """
        Cleanup the containers defined in self.sub_stuff['containers']
        """
        for name in self.sub_stuff['containers']:
            conts = self.sub_stuff['dc'].list_containers_with_name(name)
            if conts == []:
                return  # Docker was already removed
            elif len(conts) > 1:
                msg = ("Multiple containers match name '%s', not removing any"
                       " of them...", name)
                raise xceptions.DockerTestError(msg)
            DockerCmd(self, 'rm', ['--force', '--volumes', name],
                      verbose=False).execute()

    def _cleanup_async_processes(self):
        """
        Destroys all running async processes
        """
        for process in self.sub_stuff.get('async_processes', []):
            if process.executed and not process.done:
                if hasattr(process, 'close'):
                    process.close()     # close interactive pipes
                try:
                    os.kill(process.process_id, 9)
                except OSError:
                    pass
                process.wait(2)     # Give the process 2s to die

    def cleanup(self):
        super(logs_follow_base, self).cleanup()
        self._cleanup_containers()
        self._cleanup_async_processes()


class simple_base(logs_follow_base):

    """
    1. Start container
    2. Start `docker logs --follow` process
    3. Execute couple of cmds
    4. Start `docker logs` (without --follow) process
    5. Execute couple of cmds (output to stderr)
    6. Stop container
    7. Start `docker logs` (without --follow) process
    8. Check correctness o 2, then compare 2 and 7 (match) and 4 (partial
       match). Also check all exit statuses/errors/...
    """

    def _init_test_specific(self):
        """
        Initialize test-specific setting
        """
        self.sub_stuff['subargs'] = []
        raise NotImplementedError()

    def initialize(self):
        super(simple_base, self).initialize()
        self._init_test_specific()

    def wait_exists(self, name, timeout=10):
        """ Wait until container with name occurs in `docker ps` """
        conts = self.sub_stuff['dc'].list_containers_with_name(name)
        end_time = time.time() + timeout
        while time.time() < end_time:
            if len(conts) == 1:
                break
            conts = self.sub_stuff['dc'].list_containers_with_name(name)
        else:
            raise DockerTestFail("Container %s didn't start in %ss %s"
                                 % (name, timeout, conts))

    def run_once(self):
        def wait_for_output(check, output, stderr=False):
            """ Wait until check in the new output """
            idx = output.idx
            if stderr:
                output_matches = lambda: check in output.geterr(idx)
            else:
                output_matches = lambda: check in output.get(idx)
            if utils.wait_for(output_matches, 10, step=0.01) is None:
                return -1
            return 0

        def error_msg(log_us):
            """ Format a nice string from dictionary """
            out = ["%s\n%s" % (key, value)
                   for key, value in log_us.iteritems()]
            return "\n\n".join(out)

        def _output_matches(cmd1, cmd2):
            """ Compares the output of stdout&stderr """
            out1 = cmd1.stdout.splitlines() + cmd1.stderr.splitlines()
            out1 = set((_ for _ in out1 if not _.startswith('[debug]')))
            out2 = cmd2.stdout.splitlines() + cmd2.stderr.splitlines()
            out2 = set((_ for _ in out2 if not _.startswith('[debug]')))
            return out1 == out2

        super(simple_base, self).run_once()
        log_us = {}
        # Create container
        dkrcmd, name = self._init_container(self.sub_stuff['subargs'], 'bash')
        log_us['container'] = dkrcmd
        dkrcmd.execute()
        self.wait_exists(name)
        # Create docker logs --follow
        log1 = AsyncDockerCmd(self, 'logs', ['--follow', name],
                              verbose=False)
        self.sub_stuff['async_processes'].append(log1)
        log_us['log1'] = log1
        log1.execute()
        log1_out = Output(log1)
        # Generate output to stdout
        for _ in xrange(5):
            prefix = utils.generate_random_string(5)
            dkrcmd.stdin("PREFIX='%s'\n" % prefix)
            line = utils.generate_random_string(10)
            dkrcmd.stdin("echo $PREFIX: %s\n" % line)
            line = "%s: %s" % (prefix, line)
            self.failif(wait_for_output(line, log1_out),
                        "Stdout '%s' did not occur in log1 output in 10s:\n%s"
                        % (line, error_msg(log_us)))
        # Start docker logs without follow and compare output
        log2 = DockerCmd(self, 'logs', [name], verbose=False)
        log_us['log2'] = log2
        log2.execute()
        match = lambda: _output_matches(log1, log2)
        self.failif(not utils.wait_for(match, 5), "Outputs of log1 and "
                    "log2 are not the same:\n%s" % error_msg(log_us))
        # Generate output to stderr
        for _ in xrange(5):
            prefix = utils.generate_random_string(5)
            dkrcmd.stdin("PREFIX='%s'\n" % prefix)
            line = utils.generate_random_string(10)
            dkrcmd.stdin(">&2 echo $PREFIX: %s\n" % line)
            line = "%s: %s" % (prefix, line)
            self.failif(wait_for_output(line, log1_out,
                                        self.sub_stuff['stderr']),
                        "Output '%s' did not occur in log1 output in 10s:\n%s"
                        % (line, error_msg(log_us)))
        self.failif(_output_matches(log1, log2), 'Outputs log1 and log2 are '
                    "the same even thought new input was generated and log2 "
                    "was executed without --follow:\n%s" % error_msg(log_us))
        # Stop the container
        dkrcmd.stdin('exit\n')
        dkrcmd.close()
        # Wait for docker logs exit
        log1.wait(10)
        # Start docker logs without follow and compare output
        log3 = DockerCmd(self, 'logs', [name], verbose=False)
        log_us['log3'] = log3
        log3.execute()
        match = lambda: _output_matches(log1, log3)
        self.failif(not utils.wait_for(match, 5), "Outputs of log1 and "
                    "log3 are not the same:\n%s" % error_msg(log_us))


class simple(simple_base):

    """ Basic version with all streams attached and tty mode """

    def _init_test_specific(self):
        self.sub_stuff['subargs'] = ['-t', '-i']
        self.sub_stuff['stderr'] = False


class simple_no_err(simple_base):

    """ Basic version without stderr (logs should contain all) and tty mode """

    def _init_test_specific(self):
        self.sub_stuff['subargs'] = ['-t', '-i', '-a stdin', '-a stdout']
        self.sub_stuff['stderr'] = False


class simple_no_out(simple_base):

    """ Basic version without stdout (logs should contain all) and tty mode """

    def _init_test_specific(self):
        self.sub_stuff['subargs'] = ['-t', '-i', '-a stdin', '-a stderr']
        self.sub_stuff['stderr'] = False


class simple_no_tty(simple_base):

    """ Basic version with all streams attached and tty=false """

    def _init_test_specific(self):
        self.sub_stuff['subargs'] = ['-i']
        self.sub_stuff['stderr'] = True


class simple_no_tty_err(simple_base):

    """ Basic version without stderr (logs should contain all); tty=false """

    def _init_test_specific(self):
        self.sub_stuff['subargs'] = ['-i', '-a stdin', '-a stdout']
        self.sub_stuff['stderr'] = True


class simple_no_tty_out(simple_base):

    """ Basic version without stdout (logs should contain all); tty=false """

    def _init_test_specific(self):
        self.sub_stuff['subargs'] = ['-i', '-a stdin', '-a stderr']
        self.sub_stuff['stderr'] = True
