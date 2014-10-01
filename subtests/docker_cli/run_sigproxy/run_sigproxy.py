r"""
Summary
----------

Test the difference of running docker run/attach with/without '--sig-proxy'.

Operational Summary
----------------------

1. start VM with test command
2. kill $SIGNAL $test_process
3. analyze results

Configuration
-------------------------------------------
*  The ``exec_cmd`` modifies the container command
*  The ``wait_start`` is duration of container init
*  The ``kill_signals`` space separated list of signals used in test
"""
import time
from autotest.client import utils
from dockertest import config, subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd, NoFailDockerCmd
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtest
from dockertest.xceptions import DockerTestFail, DockerExecError


# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103
class run_sigproxy(subtest.SubSubtestCaller):

    """ Subtest caller """
    config_section = 'docker_cli/run_sigproxy'


class sigproxy_base(SubSubtest):

    """ Base class """

    def _init_container_normal(self, name):
        if self.sub_stuff.get('run_options_csv'):
            subargs = [arg for arg in
                       self.sub_stuff['run_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append("bash")
        subargs.append("-c")
        subargs.append(self.config['exec_cmd'])
        container = AsyncDockerCmd(self, 'run', subargs)
        self.sub_stuff['container_cmd'] = container
        container.execute()

    def _init_container_attached(self, name):
        if self.sub_stuff.get('run_options_csv'):
            subargs = [arg for arg in
                       self.sub_stuff['run_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append("bash")
        subargs.append("-c")
        subargs.append(self.config['exec_cmd'])
        container = NoFailDockerCmd(self, 'run', subargs)
        self.sub_stuff['container_cmd'] = container
        container.execute()

        if self.sub_stuff.get('attach_options_csv'):
            subargs = [arg for arg in
                       self.sub_stuff['attach_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append(name)
        container = AsyncDockerCmd(self, 'attach', subargs)
        self.sub_stuff['container_cmd'] = container  # overwrites finished cmd
        container.execute()

    def init_test_specific_variables(self):
        raise NotImplementedError("Test specific variables has to be "
                                  "overridden by child.")

    def initialize(self):
        super(sigproxy_base, self).initialize()
        self.init_test_specific_variables()
        self.sub_stuff['container_name'] = None     # tested container name
        self.sub_stuff['container_cmd'] = None      # tested container cmd
        self.sub_stuff['kill_signals'] = None        # testing kill signal
        self.sub_stuff['negative_test'] = None      # sigproxy enabled/disabled
        self.sub_stuff['check_stdout'] = self.config['check_stdout']
        config.none_if_empty(self.config)
        # Prepare a container
        docker_containers = DockerContainers(self.parent_subtest)
        name = docker_containers.get_unique_name("test", length=4)
        self.sub_stuff['container_name'] = name
        if self.sub_stuff['attached']:
            self._init_container_attached(name)
        else:
            self._init_container_normal(name)
        time.sleep(self.config['wait_start'])
        # Prepare the "sigproxy" command
        kill_sigs = [int(sig) for sig in self.config['kill_signals'].split()]
        self.sub_stuff['kill_signals'] = kill_sigs
        self.sub_stuff['negative_test'] = self.config.get('negative_test')

    def run_once(self):
        # Execute the sigproxy command
        super(sigproxy_base, self).run_once()
        container_cmd = self.sub_stuff['container_cmd']
        wait_between_kill = self.config.get('wait_between_kill')
        for signal in self.sub_stuff['kill_signals']:
            if wait_between_kill:
                time.sleep(wait_between_kill)
            utils.safe_kill(container_cmd.process_id, signal)

    def _check_results(self):
        """
        Verify that expected message was raised in the output
        """
        container_cmd = self.sub_stuff['container_cmd']
        endtime = time.time() + 5
        line = None
        out = None
        check_line = self.sub_stuff['check_stdout']
        lines = [check_line % sig for sig in self.sub_stuff['kill_signals']]
        while endtime > time.time():
            try:
                out = container_cmd.stdout.splitlines()
                for line in lines:
                    out.remove(line)
                break
            except ValueError:
                pass
        else:
            msg = ("Signal was not raised in container even though sig-proxy "
                   "was enabled:\nmissing_line:\n%s\ncontainer_out:\n%s"
                   % (line, container_cmd.stdout.splitlines()))
            raise DockerTestFail(msg)

    def postprocess(self):
        super(sigproxy_base, self).postprocess()
        self._check_results()

        # stop the container
        container_name = self.sub_stuff['container_name']
        NoFailDockerCmd(self, "kill", [container_name]).execute()
        container = self.sub_stuff['container_cmd']
        if not utils.wait_for(lambda: container.done, 5, step=0.1):
            raise DockerTestFail("Unable to kill container after test...")

    def cleanup(self):
        super(sigproxy_base, self).cleanup()
        # In case of internal failure the running container might not finish.
        failures = []
        container_cmd = self.sub_stuff.get('container_cmd')
        # container_cmd might be temporarily NoFailDockerCmd
        if (container_cmd and hasattr(container_cmd, 'done')
                and not container_cmd.done):
            utils.signal_pid(container_cmd.process_id, 15)
            if not container_cmd.done:
                utils.signal_pid(container_cmd.process_id, 9)
        if self.sub_stuff.get('container_name'):
            args = ['--force', '--volumes', self.sub_stuff['container_name']]
            try:
                NoFailDockerCmd(self, 'rm', args).execute()
            except DockerExecError, details:
                failures.append("Remove after test failed: %s" % details)
        self.failif(failures, "\n".join(failures))


class sigproxy_disabled_base(sigproxy_base):

    """
    The same test as sixproxy_base, but with sig-proxy disabled (this version
    expects signals not to be passed to the container)
    """

    def init_test_specific_variables(self):
        raise NotImplementedError("Test specific variables has to be "
                                  "overridden by child.")

    def _check_results(self):
        """
        Verify, that expected message is NOT present in the container output.
        """
        container_cmd = self.sub_stuff['container_cmd']
        endtime = time.time() + 5
        line = None
        out = None
        check_line = self.sub_stuff['check_stdout']
        bad_lines = [check_line % sig for sig
                     in self.sub_stuff['kill_signals']]
        while endtime > time.time():
            out = container_cmd.stdout.splitlines()
            for line in bad_lines:
                if line in out:
                    msg = ("Signal was raised in container even though "
                           "sig-proxy was disabled:\ncontainer_out:\n%s"
                           % out)
                    raise DockerTestFail(msg)


class default(sigproxy_base):

    """
    Test usage of docker run/attach with/without '--sig-proxy'
    * default is tty=false, sig-proxy=true
    * all signals should be forwarded properly
    """

    def init_test_specific_variables(self):
        self.sub_stuff['attached'] = False
        self.sub_stuff['run_options_csv'] = ""
        self.sub_stuff['attach_options_csv'] = ""


class tty_on_proxy_on(sigproxy_disabled_base):

    """
    Test usage of docker run/attach with/without '--sig-proxy'
    * tty should force-disable sig-proxy thus no signals should be forwarded
    """

    def init_test_specific_variables(self):
        self.sub_stuff['attached'] = False
        self.sub_stuff['run_options_csv'] = "--tty=true,--sig-proxy=true"
        self.sub_stuff['attach_options_csv'] = ""


class tty_on_proxy_off(sigproxy_disabled_base):

    """
    Test usage of docker run/attach with/without '--sig-proxy'
    * sig-proxy is disabled thus no signals should be forwarded
    """

    def init_test_specific_variables(self):
        self.sub_stuff['attached'] = False
        self.sub_stuff['run_options_csv'] = "--tty=true,--sig-proxy=false"
        self.sub_stuff['attach_options_csv'] = ""


class tty_off_proxy_on(sigproxy_base):

    """
    Test usage of docker run/attach with/without '--sig-proxy'
    * all signals should be forwarded properly
    """

    def init_test_specific_variables(self):
        self.sub_stuff['attached'] = False
        self.sub_stuff['run_options_csv'] = "--tty=false,--sig-proxy=true"
        self.sub_stuff['attach_options_csv'] = ""


class tty_off_proxy_off(sigproxy_disabled_base):

    """
    Test usage of docker run/attach with/without '--sig-proxy'
    * sig-proxy is disabled thus no signals should be forwarded
    """

    def init_test_specific_variables(self):
        self.sub_stuff['attached'] = False
        self.sub_stuff['run_options_csv'] = "--tty=false,--sig-proxy=false"
        self.sub_stuff['attach_options_csv'] = ""


class attach_default(sigproxy_base):

    """
    Test usage of docker run/attach with/without '--sig-proxy'
    * default is tty=false, sig-proxy=true
    * all signals should be forwarded properly
    """

    def init_test_specific_variables(self):
        self.sub_stuff['attached'] = True
        self.sub_stuff['run_options_csv'] = "--detach"
        self.sub_stuff['attach_options_csv'] = ""


class attach_tty_on_proxy_on(sigproxy_disabled_base):

    """
    Test usage of docker run/attach with/without '--sig-proxy'
    * tty should force-disable sig-proxy thus no signals should be forwarded
    """

    def init_test_specific_variables(self):
        self.sub_stuff['attached'] = True
        self.sub_stuff['run_options_csv'] = "--tty=true,--detach"
        self.sub_stuff['attach_options_csv'] = "--sig-proxy=true"


class attach_tty_on_proxy_off(sigproxy_disabled_base):

    """
    Test usage of docker run/attach with/without '--sig-proxy'
    * sig-proxy is disabled thus no signals should be forwarded
    """

    def init_test_specific_variables(self):
        self.sub_stuff['attached'] = True
        self.sub_stuff['run_options_csv'] = "--tty=true,--detach"
        self.sub_stuff['attach_options_csv'] = "--sig-proxy=false"


class attach_tty_off_proxy_on(sigproxy_base):

    """
    Test usage of docker run/attach with/without '--sig-proxy'
    * all signals should be forwarded properly
    """

    def init_test_specific_variables(self):
        self.sub_stuff['attached'] = True
        self.sub_stuff['run_options_csv'] = "--tty=false,--detach"
        self.sub_stuff['attach_options_csv'] = "--sig-proxy=true"


class attach_tty_off_proxy_off(sigproxy_disabled_base):

    """
    Test usage of docker run/attach with/without '--sig-proxy'
    * sig-proxy is disabled thus no signals should be forwarded
    """

    def init_test_specific_variables(self):
        self.sub_stuff['attached'] = True
        self.sub_stuff['run_options_csv'] = "--tty=false,--detach"
        self.sub_stuff['attach_options_csv'] = "--sig-proxy=false"
