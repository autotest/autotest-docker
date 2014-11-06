r"""
Summary
----------

Test docker exec by executing basic commands inside already running container
and checking the results.

Operational Summary
----------------------

#.  Test execute ``/bin/true`` in running container returning zero
#.  Test execute ``/bin/false`` in running container returning non zero
#.  Test execute ``/bin/sh`` in running container and check count of pids
#.  Test detached execute ``/bin/sh`` in running container and check count
    of pids
#.  Smoke test try to start count of containers as fast as possible in running
    container.
"""

import os
import re
import time
from autotest.client.shared import error
from autotest.client.shared import utils
from dockertest.subtest import SubSubtest, SubSubtestCaller
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.xceptions import DockerTestNAError
from dockertest.output import OutputGood
from dockertest.config import get_as_list


class AsyncDockerCmdStdIn(AsyncDockerCmd):

    r"""
    Setup a call docker subcommand as if by CLI w/ subtest config integration
    Execute docker subcommand with arguments and a timeout.

    :param subtest: A subtest.Subtest (**NOT** a SubSubtest) subclass instance
    :param subcomd: A Subcommand or fully-formed option/argument string
    :param subargs: (optional) A list of strings containing additional
                    args to subcommand
    :param timeout: Seconds to wait before terminating docker command
                    None to use 'docker_timeout' config. option.
    :param stdin_r: File descriptor for reading input data for stdin.
    :param stdin: Write part of file descriptor for reading.
    :raises DockerTestError: on incorrect usage
    """

    verbose = True

    stdin_r = None
    stdin = None

    PIPE = -1  # file descriptor should never be negative value.

    def __init__(self, subtest, subcmd, subargs=None, timeout=None,
                 verbose=True, stdin_r=None, stdin=None):
        super(AsyncDockerCmdStdIn, self).__init__(subtest, subcmd, subargs,
                                                  timeout, verbose)

        self.stdin = stdin
        if stdin_r == self.PIPE:
            self.stdin_r, self.stdin = os.pipe()

        super(AsyncDockerCmdStdIn, self).execute(self.stdin_r)

    def execute(self, stdin=None):
        """
        Unimplemented method.
        """
        raise RuntimeError('Method is not implemented')

    def close(self):
        if self.stdin_r is not None:
            os.close(self.stdin_r)
        if self.stdin is not None:
            os.close(self.stdin)


class run_exec(SubSubtestCaller):
    config_section = 'docker_cli/run_exec'


class exec_base(SubSubtest):

    fqin = None
    containers = None
    images = None
    cont = None
    img = None

    def init_subargs(self):
        self.fqin = DockerImage.full_name_from_defaults(self.config)

        run_opts = get_as_list(self.config.get("run_options_csv"))
        self.sub_stuff['run_args'] = run_opts
        name = "--name=%s" % self.sub_stuff["container_name"]
        self.sub_stuff['run_args'].append(name)
        self.sub_stuff['run_args'].append(self.fqin)
        self.sub_stuff['run_args'] += self.config['bash_cmd'].split(',')

        exec_opts = get_as_list(self.config.get("exec_options_csv"))
        self.sub_stuff['exec_args'] = exec_opts
        self.sub_stuff['exec_args'].append(self.sub_stuff["container_name"])
        self.sub_stuff['exec_args'] += self.config['exec_bash_cmd'].split(',')
        self.sub_stuff['exec_args'].append(self.config['cmd'])

    def run_cmd(self, bash_stdin, cmd):
        self.logdebug("send command to container:\n%s" % (cmd))
        os.write(bash_stdin, cmd)

    @staticmethod
    def wait_for_output(dkrcmd, pattern, timeout=120):
        got_pattern = lambda: pattern in dkrcmd.stdout
        return utils.wait_for(got_pattern,
                              timeout,
                              text='Waiting on container %s commend' % dkrcmd)

    def start_base_container(self):
        dkrcmd = AsyncDockerCmdStdIn(self, 'run', self.sub_stuff['run_args'],
                                     stdin_r=AsyncDockerCmdStdIn.PIPE)
        self.sub_stuff['dkrcmd'] = dkrcmd
        self.run_cmd(dkrcmd.stdin, "echo \"Started\"\n")
        if self.wait_for_output(dkrcmd, "Started", 10) is None:
            raise DockerTestNAError("Unable to start base container:\n %s" %
                                    (dkrcmd))
        self.containers.append(self.sub_stuff["container_name"])

    def initialize(self):
        super(exec_base, self).initialize()
        self.containers = []
        self.images = []
        self.cont = DockerContainers(self)
        self.img = DockerImages(self)
        self.sub_stuff["container_name"] = self.cont.get_unique_name()
        self.init_subargs()
        self.start_base_container()

    def postprocess(self):
        super(exec_base, self).postprocess()  # Prints out basic info
        if 'dkrcmd_exec' in self.sub_stuff:
            # Fail test if bad command or other stdout/stderr problems detected
            dkrcmd = self.sub_stuff['dkrcmd_exec']
            OutputGood(dkrcmd.cmdresult)
            expected = self.config['exit_status']
            self.failif(dkrcmd.exit_status != expected,
                        "Expected exit status: %s does not match command"
                        "exit status: %s. Details: %s" %
                        (expected, dkrcmd.exit_status, dkrcmd.cmdresult))

            self.logdebug(dkrcmd.cmdresult)

    def cleanup(self):
        super(exec_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['remove_after_test']:
            if "dkrcmd" in self.sub_stuff:
                self.sub_stuff['dkrcmd'].close()

            for cont in self.containers:
                dkrcmd = DockerCmd(self, "rm", ['--volumes', '--force', cont])
                cmdresult = dkrcmd.execute()
                msg = (" removed test container: %s" % cont)
                if cmdresult.exit_status == 0:
                    self.logdebug("Successfully" + msg)
                else:
                    self.logwarning("Failed" + msg)
            for image in self.images:
                try:
                    di = DockerImages(self.parent_subtest)
                    self.logdebug("Removing image %s", image)
                    di.remove_image_by_full_name(image)
                    self.logdebug("Successfully removed test image: %s",
                                  image)
                except error.CmdError, e:
                    error_text = "tagged in multiple repositories"
                    if error_text not in e.result_obj.stderr:
                        raise


class exec_true(exec_base):

    def run_once(self):
        super(exec_true, self).run_once()
        dkrcmd = AsyncDockerCmdStdIn(self, 'exec', self.sub_stuff['exec_args'])
        self.sub_stuff['dkrcmd_exec'] = dkrcmd
        dkrcmd.wait(120)


class exec_false(exec_true):
    pass  # Only change is in configuration


class exec_pid_count(exec_base):

    def run_once(self):
        super(exec_pid_count, self).run_once()    # Prints out basic info
        dkrcmd = AsyncDockerCmdStdIn(self, 'exec', self.sub_stuff['exec_args'],
                                     stdin_r=AsyncDockerCmdStdIn.PIPE)
        self.sub_stuff['dkrcmd_exec'] = dkrcmd
        self.run_cmd(dkrcmd.stdin, "ls -l /proc\n")
        self.wait_for_output(dkrcmd, "cmdline", 10)
        self.run_cmd(dkrcmd.stdin, "exit\n")
        dkrcmd.close()
        dkrcmd.wait(120)

    def postprocess(self):
        super(exec_pid_count, self).postprocess()  # Prints out basic info
        if 'dkrcmd_exec' in self.sub_stuff:
            # Check count of pids
            dkrcmd = self.sub_stuff['dkrcmd_exec']
            pids = re.findall("^dr.+ ([0-9]+).?$", dkrcmd.stdout, re.MULTILINE)
            self.failif(len(pids) != self.config.get("pid_count", 3),
                        "There should be exactly 3 pids in"
                        " container. Count of pid: %s" % len(pids))


class detached_pid_count(exec_base):

    def run_once(self):
        super(detached_pid_count, self).run_once()    # Prints out basic info
        dkrcmd = AsyncDockerCmdStdIn(self, 'exec', self.sub_stuff['exec_args'],
                                     stdin_r=AsyncDockerCmdStdIn.PIPE)
        self.sub_stuff['dkrcmd_exec'] = dkrcmd

        time.sleep(5)
        run_dkrcmd = self.sub_stuff['dkrcmd']
        self.run_cmd(run_dkrcmd.stdin, "ls -l /proc\n")
        self.wait_for_output(run_dkrcmd, "cmdline", 10)
        self.run_cmd(run_dkrcmd.stdin, "exit\n")
        dkrcmd.close()

    def postprocess(self):
        super(detached_pid_count, self).postprocess()  # Prints out basic info
        if 'dkrcmd_exec' in self.sub_stuff and 'dkrcmd' in self.sub_stuff:
            # Check count of pids
            dkrcmd = self.sub_stuff['dkrcmd']
            pids = re.findall("^dr.+ ([0-9]+).?$", dkrcmd.stdout, re.MULTILINE)
            self.failif(len(pids) != self.config.get("pid_count", 3),
                        "There should be exactly 3 pids in"
                        " container. Count of pid: %s\n detail: %s" %
                        (len(pids), self.sub_stuff['dkrcmd_exec']))


class smoke_pid_count(exec_base):

    def run_once(self):
        super(smoke_pid_count, self).run_once()    # Prints out basic info
        self.sub_stuff['dkrcmd_exec_list'] = []
        for _ in xrange(self.config.get("pid_count", "200") - 2):
            dkrcmd = AsyncDockerCmdStdIn(self, 'exec',
                                         self.sub_stuff['exec_args'],
                                         stdin_r=AsyncDockerCmdStdIn.PIPE)
            self.sub_stuff['dkrcmd_exec_list'].append(dkrcmd)

        time.sleep(5)
        run_dkrcmd = self.sub_stuff['dkrcmd']
        self.run_cmd(run_dkrcmd.stdin, "ls -l /proc\n")
        self.wait_for_output(run_dkrcmd, "cmdline", 10)
        self.run_cmd(run_dkrcmd.stdin, "exit\n")
        for dkrcmd in self.sub_stuff['dkrcmd_exec_list']:
            dkrcmd.close()

    def postprocess(self):
        super(smoke_pid_count, self).postprocess()  # Prints out basic info
        if 'dkrcmd_exec_list' in self.sub_stuff and 'dkrcmd' in self.sub_stuff:
            # Check count of pids
            dkrcmd = self.sub_stuff['dkrcmd']

            pids = re.findall("^dr.+ ([0-9]+).?$", dkrcmd.stdout, re.MULTILINE)
            self.failif(len(pids) != self.config.get("pid_count", 200),
                        "There should be exactly %s pids in"
                        " container. Count of pid: %s\n" %
                        (self.config.get("pid_count", 200), len(pids)))
