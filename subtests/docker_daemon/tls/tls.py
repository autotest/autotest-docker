"""
Test docker tls connection.

1) Create CA certificate
    openssl req -nodes -new -x509 -keyout ca.key -out ca.crt -days 3650 -config cacrt.conf
    echo 01 > ca.srl
2) Create certificate for daemon
    openssl req -newkey rsa -keyout server.key -out server.req -config servercrt.conf
    openssl x509 -req -days 365 -in server.req -CA ca.crt -CAkey ca.key -out server.crt
3) Create certificate for client
    openssl req -newkey rsa -keyout client.key -out client.req -config clientcrt.conf
    openssl x509 -req -days 365 -in client.req -CA ca.crt -CAkey ca.key -out client.crt -extfile extfile.cnf
4) Create wrongCA certificate
    openssl req -nodes -new -x509 -keyout ca.key -out wrongca.crt -days 3650 -config cacrt.conf
    echo 01 > ca.srl
5) Create wrong certificate for daemon
    openssl req -newkey rsa -keyout wrongserver.key -out wrongserver.req -config wrongservercrt.conf
    openssl x509 -req -days 365 -in server.req -CA wrongca.crt -CAkey wrongca.key -out wrongserver.crt
6) Create wrong certificate for client
    openssl req -newkey rsa -keyout wrongclient.key -out wrongclient.req -config wrongclientcrt.conf
    openssl x509 -req -days 365 -in wrongclient.req -CA wrongca.crt -CAkey wrongca.key -out wrongclient.crt -extfile extfile.cnf
7) Call subsubtests.
8) cleanup all containers and images.
"""

import os
import shutil
import socket
from autotest.client.shared import utils
from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers, DockerContainersCLI
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.images import DockerImage
from dockertest.config import none_if_empty, get_as_list
from dockertest.xceptions import DockerTestNAError
from dockertest import subtest
from dockertest import docker_daemon

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
        self.parent = subtest
        if isinstance(subtest, SubSubtest):
            subtest = subtest.parent_subtest

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
    config = {}

    @property
    def docker_options(self):
        """
        String of docker args
        """
        # Defined in [DEFAULTS] guaranteed to exist
        opts = get_as_list(self.parent.config['docker_options_spec'])
        opts.append("-H %s" % self.parent.config['docker_client_bind'])
        return " ".join(opts)


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
        self.parent = subtest
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


class DockerContainersCLISpec(DockerContainersCLI):
    docker_client_bind = None
    docker_options_spec = None

    def docker_cmd(self, cmd, timeout=None):
        """
        Called on to execute docker subcommand cmd with timeout

        :param cmd: Command which should be called using docker
        :param timeout: Override self.timeout if not None
        :return: autotest.client.utils.CmdResult instance
        """
        docker_cmd = ("%s %s -H %s %s" % (self.subtest.config['docker_path'],
                                          self.docker_options_spec,
                                          self.docker_client_bind,
                                          cmd))
        if timeout is None:
            timeout = self.timeout
        return utils.run(docker_cmd,
                         verbose=self.verbose,
                         timeout=timeout)


class DockerContainersE(DockerContainers):
    interfaces = {"cli_spec": DockerContainersCLISpec}


class tls(subtest.SubSubtestCaller):

    def initialize(self):
        # generate certificate
        self.prepare_tmpdir()
        self.prepare_host_dns("serverdocker9678769cfdd211e3b2fdf0def1924cda")
        self.prepare_host_dns("clientdocker9678769cfdd211e3b2fdf0def1924cda")
        os.chdir(self.tmpdir)
        self.create_CA()
        self.create_Cert("server")
        self.create_Cert("client", "extfile.cnf")
        self.create_CA(prefix="wrong")
        self.create_Cert("wrongserver", ca_prefix="wrong")
        self.create_Cert("wrongclient", "extfile.cnf", ca_prefix="wrong")

        super(tls, self).initialize()

    def prepare_tmpdir(self):
        filelist = ["cacrt.conf",
                    "clientcrt.conf",
                    "servercrt.conf",
                    "wrongcacrt.conf",
                    "wrongclientcrt.conf",
                    "wrongservercrt.conf",
                    "extfile.cnf",
                    "ca.srl",
                    "wrongca.srl"
                    ]
        for fn in filelist:
            sfpath = os.path.join(self.bindir, fn)
            dfpath = os.path.join(self.tmpdir, fn)
            shutil.copyfile(sfpath, dfpath)

    def create_CA(self, prefix=None):
        if prefix is None:
            prefix = ""
        ca = {"ca_key": "%sca.key" % prefix,
              "ca_crt": "%sca.crt" % prefix,
              "ca_conf": "%scacrt.conf" % prefix}
        results = utils.run("openssl req -nodes -new -x509"
                            " -keyout %(ca_key)s -out %(ca_crt)s"
                            " -days 3650 -config %(ca_conf)s" % (ca),
                            120, True)
        if results.exit_status:
            raise DockerTestNAError("Unable to create %sCA certificate:"
                                    "\n**STDOUT**:\n%s\n**STDERR**:\n%s" %
                                    (prefix, results.get_stdout(),
                                     results.get_stderr()))
        return results

    def create_Cert(self, cert_name, extfile=None, ca_prefix=None):
        if ca_prefix is None:
            ca_prefix = ""

        cf = {"cert_key": "%s.key" % (cert_name),
              "cert_crt": "%s.crt" % (cert_name),
              "cert_req": "%s.req" % (cert_name),
              "cert_conf": "%scrt.conf" % (cert_name),
              "ca_pref": ca_prefix,
              "cert_extra": ""}
        if extfile:
            cf["cert_extra"] = "-extfile %s" % (extfile)
        results = utils.run("openssl req -newkey rsa -keyout %(cert_key)s"
                            " -out %(cert_req)s -config %(cert_conf)s" % (cf),
                            120, True)
        if results.exit_status:
            raise DockerTestNAError("Unable to create %s certificate:"
                                    "\n**STDOUT**:\n%s\n**STDERR**:\n%s" %
                                    (cert_name, results.get_stdout(),
                                     results.get_stderr()))

        results = utils.run("openssl x509 -req -days 365 -in %(cert_req)s"
                            " -CA %(ca_pref)sca.crt -CAkey %(ca_pref)sca.key"
                            " -out %(cert_crt)s %(cert_extra)s" % (cf),
                            120, True)
        if results.exit_status:
            raise DockerTestNAError("Unable to create %s certificate:"
                                    "\n**STDOUT**:\n%s\n**STDERR**:\n%s" %
                                    (cert_name, results.get_stdout(),
                                     results.get_stderr()))
        return results

    def prepare_host_dns(self, name):
        ip = None
        try:
            ip = socket.gethostbyname(name)
        except socket.gaierror:
            pass
        if ip != "127.0.0.1" or ip is None:
            self.logwarning("/etc/hosts was changes!")
            self.stuff["hosts_back"] = open("/etc/hosts", "r").read()
            open("/etc/hosts", "a").write("127.0.0.1 %s\n" % (name))

    def cleanup(self):
        super(tls, self).cleanup()
        if "host_back" in self.stuff:
            self.logwarning("/etc/hosts was fixed!")
            open("/etc/hosts", "w").write(self.stuff["host_back"])


class tls_base(SubSubtest):
    conts = None
    images = None

    dkr_cmd = None

    def initialize(self):
        super(tls_base, self).initialize()
        none_if_empty(self.config)
        os.chdir(self.parent_subtest.tmpdir)

        bind_addr = self.config["docker_client_bind"]
        dos = " ".join(get_as_list(self.config['docker_options_spec']))

        self.conts = DockerContainersE(self.parent_subtest,
                                       interface_name="cli_spec")
        self.conts.interface.docker_client_bind = bind_addr
        self.conts.interface.docker_options_spec = dos

        self.dkr_cmd = DkrcmdFactory(self, dkrcmd_class=AsyncDockerCmdSpec)
        self.sub_stuff["image_name"] = None
        self.sub_stuff["container"] = None
        self.sub_stuff["containers"] = []
        self.sub_stuff["docker_daemon"] = None

    def cleanup(self):
        super(tls_base, self).cleanup()

        if (self.config['remove_after_test'] and
                'containers' in self.sub_stuff):
            for cont in self.sub_stuff["containers"]:
                try:
                    self.conts.remove_args = "--force --volumes"
                    self.conts.remove_by_name(cont)
                except Exception, e:
                    self.logwarning(e)

        # Kill docker_daemon process
        if self.sub_stuff["docker_daemon"] is not None:
            try:
                docker_daemon.restart_service(self.sub_stuff["docker_daemon"])
            except:
                self.failif(True, "Unable to restart docker daemon.")


class tls_verify_all_base(tls_base):

    def initialize(self):
        super(tls_verify_all_base, self).initialize()

        self.sub_stuff["check_container_name"] = True

    def run_once(self):
        super(tls_verify_all_base, self).run_once()
        # start new docker daemon
        docker_args = []
        docker_args += get_as_list(self.config["docker_daemon_args"])
        docker_args.append("-H %s" % self.config["docker_daemon_bind"])
        dd = docker_daemon.start(self.config["docker_path"], docker_args)
        ret = docker_daemon.output_match(dd)
        if not ret:
            raise DockerTestNAError("Unable to start docker daemon:"
                                    "\n**STDOUT**:\n%s\n**STDERR**:\n%s" %
                                    (dd.get_stdout(), dd.get_stderr()))
        self.sub_stuff["docker_daemon"] = dd

        if self.sub_stuff["check_container_name"]:
            self.sub_stuff["cont1_name"] = self.conts.get_unique_name("test")
            self.sub_stuff["containers"].append(self.sub_stuff["cont1_name"])
        else:
            # Try to generate name without check using docker.
            rand = utils.generate_random_string(30)
            self.sub_stuff["cont1_name"] = "test" + rand
            self.sub_stuff["containers"].append(self.sub_stuff["cont1_name"])

        # start docker client command
        fin = DockerImage.full_name_from_defaults(self.config)
        args1 = ["--name=%s" % (self.sub_stuff["cont1_name"])]
        args1.append(fin)
        args1 += ["ls", "/"]
        adc_p = AsyncDockerCmdSpec.PIPE
        self.sub_stuff["bash1"] = self.dkr_cmd.async("run", args1,
                                                     stdin_r=adc_p)
        # 1. Run with no options
        self.sub_stuff["bash1"].wait(120)

    def cleanup(self):
        super(tls_verify_all_base, self).cleanup()
        # Kill docker_daemon process
        if "bash1" in self.sub_stuff:
            self.sub_stuff["bash1"].close()


class tls_verify_all_base_bad(tls_verify_all_base):

    def initialize(self):
        super(tls_verify_all_base_bad, self).initialize()

    def cleanup(self):
        if "docker_options_spec_good" in self.config:
            dos = " ".join(get_as_list(self.config['docker_options_spec_good']))
            self.conts.interface.docker_options_spec = dos
        # Avoid warning about not exist container.
        c1 = self.conts.list_containers_with_name(self.sub_stuff["cont1_name"])
        if c1 != []:
            self.sub_stuff["containers"].remove(self.sub_stuff["cont1_name"])

        tls_verify_all_base.cleanup(self)
