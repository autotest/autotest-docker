"""
Test docker network driver.

1) restart daemon with icc=false (forbid communication)
   in network_base.initialize
2) cleanup all containers and images.
"""

import os
import time
from autotest.client import utils
from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers, DockerContainersCLI
from dockertest import subtest
from dockertest.dockercmd import AsyncDockerCmd
from dockertest import docker_daemon
from dockertest.config import none_if_empty, get_as_list
from dockertest.xceptions import DockerTestNAError


# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


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


class DockerContainersCLISpec(DockerContainersCLI):
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


class DockerContainersE(DockerContainers):
    interfaces = {"cli": DockerContainersCLISpec}


class network(subtest.SubSubtestCaller):
    config_section = 'docker_daemon/network'


class network_base(SubSubtest):
    conts = None
    images = None

    dkr_cmd = None

    def initialize(self):
        super(network_base, self).initialize()
        none_if_empty(self.config)

        bind_addr = self.config["docker_daemon_bind"]

        self.conts = DockerContainersE(self.parent_subtest)
        self.conts.interface.docker_daemon_bind = bind_addr
        self.dkr_cmd = DkrcmdFactory(self.parent_subtest,
                                     dkrcmd_class=AsyncDockerCmdSpec)
        self.sub_stuff["image_name"] = None
        self.sub_stuff["container"] = None
        self.sub_stuff["containers"] = []

        docker_args = []
        docker_args += get_as_list(self.config["docker_daemon_args"])
        docker_args.append("-H %s" % bind_addr)
        ret, dd = docker_daemon.start_docker_daemon(self.config["docker_path"],
                                                    docker_args)
        if not ret:
            raise DockerTestNAError("Unable to start docker daemon:"
                                    "\n**STDOUT**:\n%s\n**STDERR**:\n%s" %
                                    (dd.get_stdout(), dd.get_stderr()))
        self.sub_stuff["docker_daemon"] = dd


    def cleanup(self):
        super(network_base, self).cleanup()
        # Kill docker_daemon process

        if (self.config['remove_after_test'] and
                'containers' in self.sub_stuff):
            for cont in self.sub_stuff["containers"]:
                try:
                    self.conts.remove_args = "--force --volumes"
                    self.conts.remove_by_name(cont)
                except Exception, e:
                    self.logwarning(e)

        if "docker_daemon" in self.sub_stuff:
            docker_daemon.restart_docker_service(self.sub_stuff["docker_daemon"])
        # Auto-converts "yes/no" to a boolean


    def get_container_ip(self, cont_id_name):
        # Wait untils container is ready.
        json = None
        for _ in xrange(10):
            json = self.conts.get_container_metadata(cont_id_name)
            if json is not None:
                if len(json[0]["NetworkSettings"]["IPAddress"]) != 0:
                    return json[0]["NetworkSettings"]["IPAddress"]
            time.sleep(0.50)

        return None
