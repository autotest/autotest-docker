"""
Summary
-------

This test is focussed on correct handling of ``docker run --cidfile``

Operational Summary
-------------------

1.  Start container with cidfile
2.  Try to start another container with the same cidfile
3.  Exit the first container and try to start another container with the same
    cidfile
4.  Restart the original container and check the cidfile
5.  Stop the container and cleanup
"""
import os
import time

from autotest.client.shared import utils
from dockertest import config, subtest, dockercmd
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.output import mustfail
from dockertest.output import mustpass


class InteractiveAsyncDockerCmd(dockercmd.AsyncDockerCmd):

    """
    Execute docker command as asynchronous background process on ``execute()``
    with PIPE as stdin and allows use of stdin(data) to interact with process.
    """

    def __init__(self, subbase, subcmd, subargs=None, timeout=None):
        super(InteractiveAsyncDockerCmd, self).__init__(subbase, subcmd,
                                                        subargs, timeout,
                                                        verbose=True)
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

    def __del__(self):
        """ In case someone forget to run self.close()... """
        self.close()


class run_cidfile(subtest.SubSubtestCaller):

    """ SubSubtest caller """


class basic(subtest.SubSubtest):

    """ Base class """

    def _init_container(self, subargs_in, cidfile, cmd, check_method=None,
                        custom_dockercmd=None):
        """
        Starts container
        :warning: When dkrcmd_cls is of Async type, there is no guarantee
                  that it is going to be up&running after return.
        """
        def do_nothing(results):
            return results

        if custom_dockercmd is None:
            custom_dockercmd = dockercmd.DockerCmd
        if check_method is None:
            check_method = do_nothing
        if not subargs_in:
            subargs_in = []
        subargs = subargs_in[:]               # Do not modify caller's copy
        self.sub_stuff['cidfiles'].add(cidfile)
        subargs.append('--cidfile %s' % cidfile)
        name = self.sub_stuff['dc'].get_unique_name()
        self.sub_stuff['containers'].append(name)
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append(cmd)
        dkrcmd = custom_dockercmd(self, 'run', subargs)
        check_method(dkrcmd.execute())
        return dkrcmd

    def initialize(self):
        """
        Runs one container
        """
        super(basic, self).initialize()
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['containers'] = []
        self.sub_stuff['cidfiles'] = set()

    def run_once(self):
        super(basic, self).run_once()
        containers = []
        cidfile = self._nonexisting_path(self.tmpdir, "cidfile-")
        subargs = self.config.get('run_options_csv').split(',')
        containers.append(self._init_container(subargs, cidfile, 'sh', None,
                                               InteractiveAsyncDockerCmd))
        name = self.sub_stuff['containers'][0]
        self.failif(utils.wait_for(lambda: os.path.isfile(cidfile), 9) is None,
                    "cidfile didn't appear in 9s after container execution")
        cont = self._get_container_by_name(name)
        long_id = cont.long_id
        self._check_cidfile(long_id, cidfile)
        # cidfile already exists (running container)
        containers.append(self._init_container(subargs, cidfile, 'true',
                                               lambda x: mustfail(x, 125)))
        self._check_failure_cidfile_present(containers[-1])
        # cidfile already exists (exited container)
        # FIXME: this occasionally throws SIGPIPE, presumably because
        #  container isn't fully ready. This is a tough one to solve.
        containers[0].stdin("exit\n")
        containers[0].wait(10)
        containers[0].close()
        containers.append(self._init_container(subargs, cidfile, 'true',
                                               lambda x: mustfail(x, 125)))
        self._check_failure_cidfile_present(containers[-1])
        # restart container with cidfile
        mustpass(dockercmd.DockerCmd(self, 'start', [name]).execute())
        is_alive = lambda: 'Up' in self._get_container_by_name(name).status
        self.failif(utils.wait_for(is_alive, 10) is None, "Container %s "
                    "was not restarted in 10 seconds." % name)
        self._check_cidfile(long_id, cidfile)
        self.sub_stuff['dc'].kill_container_by_name(name)
        self._check_cidfile(long_id, cidfile)

    def _check_failure_cidfile_present(self, dkrcmd):
        """ Check that docker warns about existing cidfile """
        msg_cidfile_exists = self.config['docker_msg_cidfile_exists']
        self.failif(msg_cidfile_exists not in dkrcmd.cmdresult.stderr, "Msg "
                    "'%s' not present in the container stderr:\n%s"
                    % (msg_cidfile_exists, dkrcmd))

    def _get_container_by_name(self, name):
        """ Runs 'docker ps' until desired named container is found """
        found = [[]]                 # python2 hack for scope within closure

        def find_container():
            found[0] = self.sub_stuff['dc'].list_containers_with_name(name)
            return len(found[0]) == 1

        ok = utils.wait_for(find_container, 10)
        self.failif(not ok, "Timed out waiting for container '%s'" % name)
        return found[0][0]

    def _nonexisting_path(self, path, prefix):
        """ generate non-existing file name """
        for _ in xrange(1000):
            name = prefix + utils.generate_random_string(8)
            if not os.path.isfile(os.path.join(path, name)):
                return os.path.join(path, name)
        self.failif(True, "Unable to generate nonexisting cidfile in 1000 "
                    "iterations (%s, %s)" % (path, prefix))

    def _check_cidfile(self, long_id, cidfile):
        """ check id from cidfile with long_id """
        act = ""
        for _ in xrange(5):
            act = open(cidfile, 'r').read()
            if act != "":
                break
            time.sleep(1)
        self.failif_ne(long_id, act, "Cidfile output")

    def _cleanup_cidfiles(self):
        """ Unlink all used cidfiles """
        for name in self.sub_stuff.get('cidfiles', []):
            if os.path.exists(name):
                os.unlink(name)

    def cleanup(self):
        super(basic, self).cleanup()
        if self.config['remove_after_test']:
            self._cleanup_cidfiles()
            dc = DockerContainers(self)
            dc.clean_all(self.sub_stuff.get('containers', []))
