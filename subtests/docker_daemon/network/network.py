r"""
Summary
----------

This a set of test that check the container's network security.

Operational Summary
----------------------

#. restart daemon with icc=false (forbid communication)
   in network_base.initialize
#. start container1 and get their ip addr
#. Try to connect containers with python
#. fail if communication pass from container2 to container1

Prerequisites
------------------------------------------
*  Docker is installed in host system.
*  Container os has installed python package.
*  Command iptable and brctl are working well.
"""

import os
from autotest.client import utils
from autotest.client.shared import error
from dockertest.subtest import SubSubtest, SubSubtestCaller
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd
from dockertest import docker_daemon
from dockertest.config import none_if_empty, get_as_list
from dockertest.xceptions import DockerTestNAError


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

        self.execute()

    # pylint: disable=W0221
    def execute(self):
        super(AsyncDockerCmdStdIn, self).execute(self.stdin_r)

    def close(self):
        if self.stdin_r is not None:
            os.close(self.stdin_r)
        if self.stdin is not None:
            os.close(self.stdin)


class AsyncDockerCmdSpec(AsyncDockerCmdStdIn):

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

    @property
    def docker_options(self):
        """
        String of docker args
        """

        # Defined in [DEFAULTS] guaranteed to exist
        return self.subtest.config['docker_options_spec']


class DkrcmdFactory(object):

    r"""
    DockerCmd factory create dockercmd object with specified subtest and more.
    Simplifies DockerCmd because replace blocking calling of docker by
    async calling and waiting.

    :param subtest: A subtest.Subtest (**NOT** a SubSubtest) subclass instance
    :param verbose: set verbosity
    :param timeout: set default timeout
    :param dkrcmd_class: set default docker cmd class.
    """
    dkrcmd_class = AsyncDockerCmdStdIn

    def __init__(self, subtest, verbose=True, timeout=None, dkrcmd_class=None):
        self.subtest = subtest
        self.verbose = verbose
        if dkrcmd_class:
            self.dkrcmd_class = dkrcmd_class
        if timeout:
            self.dkrcmd_class.timeout = timeout

    def __call__(self, subcmd, subargs=None, timeout=None, verbose=True,
                 **kargs):
        r"""
        Create new DockerCmd object and wait for finishing.

        :param subcomd: A Subcommand or fully-formed option/argument string
        :param subargs: (optional) A list of strings containing additional
                        args to subcommand
        :param timeout: Seconds to wait before terminating docker command
                        None to use 'docker_timeout' config. option.
        :param stdin_r: File descriptor for reading input data for stdin.
        :param stdin: Write part of file descriptor for reading.
        :return: DockerCmd object.
        """
        cmd = self.async(subcmd, subargs, timeout, verbose, **kargs)
        cmd.wait(timeout)
        return cmd

    def async(self, subcmd, subargs=None, timeout=None, verbose=True,
              **kargs):
        r"""
        Create new DockerCmd object.

        :param subcomd: A Subcommand or fully-formed option/argument string
        :param subargs: (optional) A list of strings containing additional
                        args to subcommand
        :param timeout: Seconds to wait before terminating docker command
                        None to use 'docker_timeout' config. option.
        :param stdin_r: File descriptor for reading input data for stdin.
        :param stdin: Write part of file descriptor for reading.
        :return: DockerCmd object.
        """
        return self.dkrcmd_class(self.subtest, subcmd, subargs, timeout,
                                 verbose, **kargs)


class DockerContainersSpec(DockerContainers):
    docker_daemon_bind = None

    def docker_cmd(self, cmd, timeout=None):
        """
        Called on to execute docker subcommand cmd with timeout

        :param cmd: Command which should be called using docker
        :param timeout: Override self.timeout if not None
        :return: autotest.client.utils.CmdResult instance
        """
        docker_cmd = ("%s -H %s %s" % (self.subtest.config['docker_path'],
                                       self.docker_daemon_bind,
                                       cmd))
        if timeout is None:
            timeout = self.timeout
        return utils.run(docker_cmd,
                         verbose=self.verbose,
                         timeout=timeout)


class network(SubSubtestCaller):
    config_section = 'docker_daemon/network'


class network_base(SubSubtest):

    dkr_cmd = None

    def initialize(self):
        super(network_base, self).initialize()
        none_if_empty(self.config)

        bind_addr = self.config["docker_daemon_bind"]

        conts = DockerContainersSpec(self)
        self.sub_stuff['conts'] = conts
        conts.docker_daemon_bind = bind_addr
        self.dkr_cmd = DkrcmdFactory(self, dkrcmd_class=AsyncDockerCmdSpec)
        self.sub_stuff["image_name"] = None
        self.sub_stuff["container"] = None
        self.sub_stuff["containers"] = []

        docker_args = []
        docker_args += get_as_list(self.config["docker_daemon_args"])
        docker_args.append("-H %s" % bind_addr)
        self.loginfo("Starting %s %s", self.config["docker_path"], docker_args)
        dd = docker_daemon.start(self.config["docker_path"],
                                 docker_args)
        if not docker_daemon.output_match(dd):
            raise DockerTestNAError("Unable to start docker daemon:"
                                    "\n**STDOUT**:\n%s\n**STDERR**:\n%s" %
                                    (dd.get_stdout(), dd.get_stderr()))
        self.sub_stuff["docker_daemon"] = dd

    def cleanup(self):
        super(network_base, self).cleanup()
        # Kill docker_daemon process
        conts = self.sub_stuff['conts']
        # Auto-converts "yes/no" to a boolean
        if (self.config['remove_after_test'] and
                'containers' in self.sub_stuff):
            for cont in self.sub_stuff["containers"]:
                try:
                    conts.remove_args = "--force --volumes"
                    conts.remove_by_name(cont)
                except (ValueError, error.CmdError), e:
                    self.logdebug(e)

        if "docker_daemon" in self.sub_stuff:
            docker_daemon.restart_service(
                self.sub_stuff["docker_daemon"])

    def get_jason(self, cont_name):
        try:
            return self.sub_stuff['conts'].json_by_name(cont_name)
        except ValueError:
            return None  # container not up yet

    def get_container_ip(self, cont_name):
        # Wait untils container is ready.
        got_json = lambda: self.get_jason(cont_name)
        utils.wait_for(got_json,
                       120,
                       text='Waiting on container %s start' % cont_name)
        json = self.get_jason(cont_name)
        if len(json) == 1:
            netset = json[0].get("NetworkSettings")
            if netset is not None:
                return netset.get("IPAddress")  # Could return None
        return None
