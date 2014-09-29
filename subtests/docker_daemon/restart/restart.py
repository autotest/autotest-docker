r"""
Summary
----------
Test docker restart check if the docker daemon behave properly during restart.

Operational Summary
---------------------

#.  Test docker container autorestart after docker dameon restart.
#.  Test docker infinity uninteruptable container autorestart after docker
    daemon restart.
#.  Test stop of docker daemon and check if there left some "mess".
"""

import os
import re
import time
from autotest.client.shared import utils
from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.images import DockerImage
from dockertest import docker_daemon
from dockertest.config import none_if_empty, get_as_list
from dockertest import subtest
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

    def __init__(self, _subtest, subcmd, subargs=None, timeout=None,
                 verbose=True, stdin_r=None, stdin=None):
        self.parent = _subtest
        if isinstance(_subtest, SubSubtest):
            _subtest = _subtest.parent_subtest

        super(AsyncDockerCmdStdIn, self).__init__(_subtest, subcmd, subargs,
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
            self.stdin_r = None
        if self.stdin is not None:
            os.close(self.stdin)
            self.stdin = None


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

    def __init__(self, _subtest, verbose=True, timeout=None,
                 dkrcmd_class=None):
        self.parent = _subtest
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
        cmd = self.dkrcmd_class(self.parent, subcmd, subargs, timeout,
                                verbose, **kargs)
        return cmd


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


class restart(subtest.SubSubtestCaller):

    def initialize(self):
        # generate certificate
        super(restart, self).initialize()


class restart_base(SubSubtest):
    conts = None
    images = None

    dkr_cmd = None

    def initialize(self):
        super(restart_base, self).initialize()
        none_if_empty(self.config)

        bind_addr = self.config["docker_daemon_bind"]

        self.conts = DockerContainersSpec(self)
        self.conts.docker_daemon_bind = bind_addr

        self.dkr_cmd = DkrcmdFactory(self, dkrcmd_class=AsyncDockerCmdSpec)
        self.sub_stuff["image_name"] = None
        self.sub_stuff["container"] = None
        self.sub_stuff["containers"] = []

        # Necessary for avoid conflict with service manager. [docker.socket]
        docker_args = []
        docker_args += get_as_list(self.config["docker_daemon_args"])
        docker_args.append("-H %s" % bind_addr)
        if self.config.get("new_docker_graph_path"):
            self.sub_stuff["graph_path"] = os.path.join(self.tmpdir, "graph")
            docker_args.append("-g %s" % self.sub_stuff["graph_path"])

        self.sub_stuff["dd_args"] = docker_args

        self.loginfo("Starting %s %s", self.config["docker_path"], docker_args)
        dd = docker_daemon.start(self.config["docker_path"],
                                 docker_args)
        if not docker_daemon.output_match(dd):
            raise DockerTestNAError("Unable to start docker daemon:"
                                    "\n**STDOUT**:\n%s\n**STDERR**:\n%s" %
                                    (dd.get_stdout(), dd.get_stderr()))
        self.sub_stuff["docker_daemon"] = dd

    def daemon_stop(self):
        self.sub_stuff["docker_daemon"].kill_func()
        self.sub_stuff["docker_daemon"].wait_for(30)

    def daemon_start(self):
        cmd = [self.config["docker_path"]]
        cmd += self.sub_stuff["dd_args"]
        daemon_process = utils.AsyncJob(" ".join(cmd), close_fds=True)
        self.sub_stuff["docker_daemon"] = daemon_process

        if not docker_daemon.output_match(daemon_process):
            raise DockerTestNAError("Unable to start docker daemon:"
                                    "\n**STDOUT**:\n%s\n**STDERR**:\n%s" %
                                    (daemon_process.get_stdout(),
                                     daemon_process.get_stderr()))

    def daemon_restat(self):
        self.daemon_stop()
        self.daemon_start()

    def cleanup(self):
        super(restart_base, self).cleanup()

        if (self.config['remove_after_test'] and
                'containers' in self.sub_stuff):
            for cont in self.sub_stuff["containers"]:
                for _ in xrange(3):
                    try:
                        # pylint: disable=W0201
                        self.conts.remove_args = "--stop --volumes"
                        self.conts.remove_by_name(cont)
                    except Exception, e:  # pylint: disable=W0703
                        self.logwarning(e)
                        time.sleep(5)
                        continue
                    break

        if "docker_daemon" in self.sub_stuff:
            docker_daemon.restart_service(
                self.sub_stuff["docker_daemon"])


class restart_container_autorestart_base(restart_base):

    def initialize(self):
        super(restart_container_autorestart_base, self).initialize()

        c_name = self.conts.get_unique_name("test")
        self.sub_stuff["cont1_name"] = c_name
        self.sub_stuff["containers"].append(c_name)

    def run_once(self):
        super(restart_container_autorestart_base, self).run_once()

        fin = DockerImage.full_name_from_defaults(self.config)
        args1 = ["--name=%s" % (self.sub_stuff["cont1_name"])]
        args1.append(fin)
        if self.config.get('interruptable'):
            args1 += ["python", "-c", "'import signal; "
                      "signal.signal(signal.SIGTERM, exit); signal.pause()'"]
        else:
            args1 += ["bash", "-c", '"while [ true ]; do sleep 1; done"']
        self.sub_stuff["bash1"] = self.dkr_cmd.async("run", args1)

        # Wait for container creation
        c_name = self.sub_stuff["cont1_name"]
        wait_cont = lambda: self.conts.list_containers_with_name(c_name) != []
        ret = utils.wait_for(wait_cont, 240)
        self.failif(ret is None, "Unable to start container.")

        self.daemon_restat()

    def cleanup(self):
        # Start of docker bug workaround
        # https://bugzilla.redhat.com/show_bug.cgi?id=1126874
        if "cont1_name" in self.sub_stuff:
            res = utils.run("mount")
            cont = self.conts.get_container_metadata(
                self.sub_stuff["cont1_name"])

            if cont[0]["Id"] in res.stdout:
                self.logerror("Workaround docker bug! Have to manually unmount"
                              " container disk.")
                mounted = re.findall(r"^(\S+%s)\s*.*" % cont[0]["Id"],
                                     res.stdout, re.MULTILINE)
                res = utils.run("umount %s" % mounted[0])

        # Stop of docker bug workaround
        super(restart_container_autorestart_base, self).cleanup()
        # Kill docker_daemon process
        if "bash1" in self.sub_stuff:
            self.sub_stuff["bash1"].close()


class restart_check_mess_after_stop_base(restart_base):

    def initialize(self):
        super(restart_check_mess_after_stop_base, self).initialize()
        c_name = self.conts.get_unique_name("test")
        self.sub_stuff["cont1_name"] = c_name
        self.sub_stuff["containers"].append(c_name)

    def run_once(self):
        super(restart_check_mess_after_stop_base, self).run_once()

        fin = DockerImage.full_name_from_defaults(self.config)
        args1 = ["--name=%s" % (self.sub_stuff["cont1_name"])]
        args1.append(fin)
        args1 += ["echo", "hello"]
        self.sub_stuff["bash1"] = self.dkr_cmd("run", args1, 480)

        self.sub_stuff["bash1"].close()
        # Stop docker daemon.
        self.daemon_stop()

    def cleanup(self):
        self.daemon_start()
        super(restart_check_mess_after_stop_base, self).cleanup()
        # Kill docker_daemon process
