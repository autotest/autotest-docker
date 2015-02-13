r"""
Summary
---------

This test checks function of `docker run -e VARIABLE=VALUE ...`.
Also verifies the rm --link operation with ICC.

Operational Summary
----------------------

#. Setup client & server containers w/ exposed port and env. vars.
#. Run code in containers to verify communication and env. vars
#. Check results match expectations

Operational Detail
----------------------

The port test
~~~~~~~~~~~~~~~
#.  Starts server with custom -e ENV_VARIABLE=$RANDOM_STRING and opened port
#.  Starts client linked to server with another ENV_VARIABLE
#.  Booth prints the env as {}
#.  Client sends data to server (addr from env SERVER_PORT_$PORT_TCP_ADDR)
#.  Server prints data with prefix and resends them back with another one.
#.  Client prints the received data and finishes.
#.  Checks if env and all data were printed correctly.

The rm_link test
~~~~~~~~~~~~~~~~~
#.  Same as port (above), however after container is started, the
    rm --link command is issued to remove the connecting link.
#.  Verify communication between containers was prevented
#.  Also conclude with same checks as in port (above)

Prerequisites
---------------

Docker daemon and host-networking setup to allow ICC between containers.
If iptables is involved, and bridge-networking is in use, verify these
sysctl's are set to ``1``:

    * net.bridge.bridge-nf-call-arptables
    * net.bridge.bridge-nf-call-ip6tables
    * net.bridge.bridge-nf-call-iptables
"""
import ast
import os.path
import random
import re

from autotest.client import utils
from dockertest import config
from dockertest import docker_daemon
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.output import mustpass
from dockertest.config import get_as_list
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtestCaller, SubSubtest
from dockertest.output import wait_for_output


class InteractiveAsyncDockerCmd(AsyncDockerCmd):

    """
    Execute docker command as asynchronous background process on ``execute()``
    with PIPE as stdin and allows use of stdin(data) to interact with process.
    """

    stdin_by_lines = True
    guarantee_newlines = True

    def __init__(self, subtest, subcmd, subargs=None, timeout=None,
                 verbose=True):
        super(InteractiveAsyncDockerCmd, self).__init__(subtest, subcmd,
                                                        subargs, timeout,
                                                        verbose)
        self._stdin = None

    def execute(self, stdin=None):
        """
        Start execution of asynchronous docker command
        """
        ps_stdin, self._stdin = os.pipe()
        ret = super(InteractiveAsyncDockerCmd, self).execute(ps_stdin)
        os.close(ps_stdin)
        self.stdin = stdin
        return ret

    @property
    def stdin(self):
        """
        Return open file instance connected to processes stdin
        """
        return self._stdin

    @stdin.setter
    def stdin(self, data):
        """
        Sends data to stdin (partial send is possible!)
        :param data: Data to be send
        :return: Number of written data
        """
        if data:
            if self.stdin_by_lines:
                for line in str(data).splitlines(True):  # Preserve '\n'
                    if self.guarantee_newlines:
                        # Make sure every (or only) line ends with '\n'
                        if line[-1] != '\n':
                            line += '\n'
                    os.write(self._stdin, line)
            else:
                os.write(self._stdin, data)

    def close(self):
        """
        Close the pipes (when opened)
        """
        if self._stdin:
            os.close(self._stdin)
            self._stdin = None


class run_env(SubSubtestCaller):

    """ Subtest caller """


class run_env_base(SubSubtest):

    """ Base class """

    # Note: requires: container, port, data
    python_client = (
        """import sys\n"""
        """import socket\n"""
        """import os\n"""
        """# run_env_base.get_env() depends on this behavior\n"""
        """\n"""
        """print "ENVIRON = " + str(os.environ)\n"""
        """addr = os.environ['%(container)s_PORT_%(port)s_TCP_ADDR']\n"""
        """sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"""
        """# port.run_once() depends on this output, not statement\n"""
        """\n"""
        """print "Client", "Connecting"\n"""
        """sock.connect((addr, %(port)s))\n"""
        """sock.send("%(data)s")\n"""
        """print sock.recv(1024)\n"""
        """sock.close()\n"""
        """\n"""
        """sys.exit(0)\n"""
    )

    # Note: requires: port
    python_server = (
        """import sys\n"""
        """import socket\n"""
        """import os\n"""
        """# run_env_base.get_env() depends on this behavior\n"""
        """\n"""
        """print "ENVIRON = " + str(os.environ)\n"""
        """sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"""
        """sock.bind(("", %(port)s))\n"""
        """sock.listen(True)\n"""
        """# port.run_once() depends on this output, not statement\n"""
        """\n"""
        """print "Server", "Listening"\n"""
        """conn, addr = sock.accept()\n"""
        """print "Connected by", addr\n"""
        """data = conn.recv(1024)\n"""
        """print "RECEIVED: " + data\n"""
        """conn.send("RESENDING: " + data)\n"""
        """\n"""
        """conn.close()\n"""
        """\n"""
        """sys.exit(0)\n"""
    )

    def record_iptables(self, label):
        name = ('%s_iptables_%s.txt'
                % (self.__class__.__name__, label))
        output = open(os.path.join(self.parent_subtest.resultsdir, name), 'w+')
        output.write(utils.run('iptables -t filter -L -n -v').stdout)
        output.write('\n\n')
        output.write(utils.run('iptables -t nat -L -n -v').stdout)

    def get_env(self, output):
        """
        Check output for token, return value as if parsed in python
        """
        for line in output.splitlines():
            if line.startswith('ENVIRON = {'):
                return ast.literal_eval(line[10:])
        self.failif(True, "Fail to get env from output\n%s" % output)

    def check_env(self, exp, variable, env, container, appendix):
        """
        Check that variable's value matches the exp regexp. Fails the test
        when it's not.
        :param exp: Expected value (string)
        :param variable: Name of the env variable (string)
        :param env: Environment (dictionary)
        :param container: Name of the container (string)
        :param appendix: Rest of the error string
        """
        self.failif(not re.match(exp, env.get(variable)), "%s=%s not found in"
                    " %s env:\n%s%s" % (variable, exp, container, env,
                                        appendix))

    def init_container(self, prefix, subargs, cmd):
        """
        Prepares dkrcmd and stores the name in self.sub_stuff['containers']
        :return: tuple(dkrcmd, name)
        """
        name = self.sub_stuff['dc'].get_unique_name(prefix)
        subargs.append("--name %s" % name)
        self.logdebug("Queuing container %s for removal", name)
        self.sub_stuff['containers'].append(name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append(cmd)
        dkrcmd = InteractiveAsyncDockerCmd(self, 'run', subargs)
        dkrcmd.verbose = True
        dkrcmd.quiet = False
        return dkrcmd, name

    def initialize(self):
        super(run_env_base, self).initialize()
        # Prepare a container
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['containers'] = []

    def cleanup(self):
        super(run_env_base, self).cleanup()
        if not self.config['remove_after_test']:
            return
        for name in self.sub_stuff.get('containers', []):
            self.logdebug("Killing %s", name)
            DockerCmd(self, 'kill', [name]).execute()
            self.logdebug("Removing %s", name)
            DockerCmd(self, 'rm', ['--force', '--volumes', name],
                      verbose=False).execute()


class port_base(run_env_base):

    """
    Base class for port test.
    """

    def initialize(self):
        super(port_base, self).initialize()
        self.sub_stuff['server_env'] = utils.generate_random_string(8)
        params = {'port': random.randrange(4000, 5000),
                  'container': 'SERVER',
                  'data': ('Testing data %s'
                           % utils.generate_random_string(12))}
        self.sub_stuff['params'] = params
        self.sub_stuff['client_env'] = utils.generate_random_string(6)

    def start_server(self):
        params = self.sub_stuff['params']
        subargs = get_as_list(self.config['server_options'])
        subargs += ['--publish %s' % params['port'],
                    '-e ENV_VARIABLE=%s' % self.sub_stuff['server_env']]
        cmd = 'python ' + ' '.join(get_as_list(self.config['python_options']))
        servercmd, server = self.init_container('server', subargs, cmd)
        self.sub_stuff['server_name'] = server
        servercmd.execute()
        return servercmd

    def start_client(self):
        server_name = self.sub_stuff['server_name']
        subargs = get_as_list(self.config['client_options'])
        subargs += ['--link %s:server' % server_name,
                    '--env ENV_VARIABLE=%s' % self.sub_stuff['client_env']]
        cmd = 'python ' + ' '.join(get_as_list(self.config['python_options']))
        clientcmd, client = self.init_container('client', subargs, cmd)
        self.sub_stuff['client_name'] = client
        clientcmd.execute()
        return clientcmd

    def remove_link(self, client_name, alias):
        return mustpass(DockerCmd(self,
                                  'rm',
                                  ['--link=true',
                                   '%s/%s' % (client_name, alias)]).execute())

    def wait_for(self, dkrcmd, what, fail_msg, negative=False, stderr=False):
        if stderr:
            func = lambda: dkrcmd.stderr
        else:
            func = lambda: dkrcmd.stdout
        self.failif(negative == wait_for_output(func, what), fail_msg)


class port(port_base):

    """
    1. Starts server with custom -e ENV_VARIABLE=$RANDOM_STRING and opened port
    2. Starts client linked to server with another ENV_VARIABLE
    3. Booth prints the env as {}
    4. Client sends data to server (addr from env SERVER_PORT_$PORT_TCP_ADDR)
    5. Server prints data with prefix and resends them back with another one.
    6. Client prints the received data and finishes.
    7. Checks if env and all data were printed correctly.
    """

    def run_once(self):
        super(port, self).run_once()
        params = self.sub_stuff['params']
        # Server needs to be listening before client tries to connect
        servercmd = self.start_server()
        # Container running properly when python prompt appears
        self.logdebug("Waiting for server's python prompt")
        self.wait_for(servercmd,
                      '>>> ',
                      "No python prompt from server\n%s" % servercmd,
                      stderr=True)
        servercmd.stdin = str(self.python_server % params)  # str() for clarity
        # Executed python prints this on stdout
        self.logdebug("Waiting for server to start listening")
        self.wait_for(servercmd, 'Server Listening', "Server not listening")
        clientcmd = self.start_client()
        self.logdebug("Waiting for client's python prompt")
        self.wait_for(clientcmd,
                      '>>> ',
                      "No python prompt from client\n%s" % clientcmd,
                      stderr=True)
        clientcmd.stdin = str(self.python_client % params)
        # Executed python includes printing this on stdout
        self.logdebug("Waiting for client to connect")
        self.wait_for(clientcmd,
                      "Client Connecting",
                      "No client connect\n%s" % clientcmd)
        # Client will probably exit first
        self.sub_stuff['client_result'] = clientcmd.wait(5)
        self.sub_stuff['server_result'] = servercmd.wait(5)
        # Order shouldn't matter here
        clientcmd.close()
        servercmd.close()

    def postprocess(self):
        super(port, self).postprocess()
        client_res = self.sub_stuff['client_result']
        server_res = self.sub_stuff['server_result']
        err_str = "\n\nServer\n%s\n\nClient\n%s" % (server_res, client_res)
        # server env
        server_env = self.get_env(server_res.stdout)
        self.check_env(self.sub_stuff['server_env'], 'ENV_VARIABLE',
                       server_env, 'server', err_str)

        # client env
        client_env = self.get_env(client_res.stdout)
        self.check_env(self.sub_stuff['client_env'], 'ENV_VARIABLE',
                       client_env, 'client', err_str)
        # linked client env
        self.check_env("/%s/server" % self.sub_stuff['client_name'],
                       'SERVER_NAME', client_env, 'client', err_str)
        self.check_env(self.sub_stuff['server_env'], 'SERVER_ENV_ENV_VARIABLE',
                       client_env, 'client', err_str)
        addr = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        serv_port = str(self.sub_stuff['params']['port'])
        self.check_env("tcp://%s:%s" % (addr, serv_port), 'SERVER_PORT',
                       client_env, 'client', err_str)
        self.check_env("tcp://%s:%s" % (addr, serv_port), 'SERVER_PORT_%s_TCP'
                       % serv_port, client_env, 'client', err_str)
        self.check_env(addr, 'SERVER_PORT_%s_TCP_ADDR' % serv_port,
                       client_env, 'client', err_str)
        self.check_env(serv_port, 'SERVER_PORT_%s_TCP_PORT' % serv_port,
                       client_env, 'client', err_str)
        self.check_env('tcp', 'SERVER_PORT_%s_TCP_PROTO' % serv_port,
                       client_env, 'client', err_str)
        # data on server
        data = self.sub_stuff['params']['data']
        exp = "RECEIVED: %s" % data
        self.failif(exp not in server_res.stdout, "Data '%s' sent from client "
                    "were not received on server:\n%s" % (exp, err_str))
        # data on client
        exp = "RESENDING: %s" % data
        self.failif(exp not in client_res.stdout, "Data '%s' sent from server "
                    "were not received on client:\n%s" % (exp, err_str))


class rm_link(port_base):

    """
    1. Starts server with custom -e ENV_VARIABLE=$RANDOM_STRING and opened port
    2. Starts client linked to server with another ENV_VARIABLE
    3. Booth prints the env as {}
    4. Remove link from server -> client
    5. Client times out connecting to server.
    5. Server times out waiting for client
    7. Checks if env and no data printed correctly.
    """

    def initialize(self):
        self.record_iptables('initial')
        self.logdebug('Restarting docker daemon w/ --icc=false')
        daemon_options = get_as_list(self.config['daemon_options'])
        daemon_options.append('--icc=false')
        self.sub_stuff['dd'] = docker_daemon.start(self.config['docker_path'],
                                                   daemon_options)
        self.failif(not docker_daemon.output_match(self.sub_stuff['dd']))
        super(rm_link, self).initialize()

    def run_once(self):
        super(rm_link, self).run_once()
        params = self.sub_stuff['params']
        # Server needs to be listening before client tries to connect
        servercmd = self.start_server()
        # Container running properly when python prompt appears
        self.logdebug("Waiting for server's python prompt")
        self.wait_for(servercmd,
                      '>>> ',
                      "No python prompt from server\n%s" % servercmd,
                      stderr=True)
        self.logdebug("Executing server code...")
        servercmd.stdin = str(self.python_server % params)  # str() for clarity
        self.logdebug("Waiting for server to start listening")
        self.wait_for(servercmd, "Server Listening",
                      "No 'Server Listenting' found in stdout")
        clientcmd = self.start_client()
        self.logdebug("Waiting for client's python prompt")
        self.wait_for(clientcmd,
                      '>>> ',
                      "No python prompt from client\n%s" % clientcmd,
                      stderr=True)

        # To help troubleshoot iptables related problems
        self.record_iptables('before_rmlink')

        self.remove_link(self.sub_stuff['client_name'], 'server')

        self.record_iptables('after_rmlink')

        clientcmd.stdin = str(self.python_client % params)
        # Executed python includes printing this on stdout
        self.logdebug("Waiting for client to connect")
        self.wait_for(clientcmd,
                      "Client Connecting",
                      "No client connect\n%s" % clientcmd)
        msg = ("Negative test, but reply received: '%s'" % clientcmd.stdout)
        self.wait_for(clientcmd, 'RESENDING: ', msg, negative=True)
        self.sub_stuff['client_result'] = clientcmd.wait(5)
        self.sub_stuff['server_result'] = servercmd.wait(5)
        # Order shouldn't matter here
        clientcmd.close()
        servercmd.close()

    def postprocess(self):
        super(rm_link, self).postprocess()
        client_res = self.sub_stuff['client_result']
        server_res = self.sub_stuff['server_result']
        err_str = "\n\nServer\n%s\n\nClient\n%s" % (server_res, client_res)
        # server env
        server_env = self.get_env(server_res.stdout)
        self.check_env(self.sub_stuff['server_env'], 'ENV_VARIABLE',
                       server_env, 'server', err_str)

        # client env
        client_env = self.get_env(client_res.stdout)
        self.check_env(self.sub_stuff['client_env'], 'ENV_VARIABLE',
                       client_env, 'client', err_str)
        # linked client env
        self.check_env("/%s/server" % self.sub_stuff['client_name'],
                       'SERVER_NAME', client_env, 'client', err_str)
        self.check_env(self.sub_stuff['server_env'], 'SERVER_ENV_ENV_VARIABLE',
                       client_env, 'client', err_str)
        addr = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        serv_port = str(self.sub_stuff['params']['port'])
        self.check_env("tcp://%s:%s" % (addr, serv_port), 'SERVER_PORT',
                       client_env, 'client', err_str)
        self.check_env("tcp://%s:%s" % (addr, serv_port), 'SERVER_PORT_%s_TCP'
                       % serv_port, client_env, 'client', err_str)
        self.check_env(addr, 'SERVER_PORT_%s_TCP_ADDR' % serv_port,
                       client_env, 'client', err_str)
        self.check_env(serv_port, 'SERVER_PORT_%s_TCP_PORT' % serv_port,
                       client_env, 'client', err_str)
        self.check_env('tcp', 'SERVER_PORT_%s_TCP_PROTO' % serv_port,
                       client_env, 'client', err_str)
        # data on server
        data = self.sub_stuff['params']['data']
        exp = "RECEIVED: %s" % data
        self.failif(exp in server_res.stdout, "Data '%s' sent from client "
                    "were not received on server:\n%s" % (exp, err_str))
        # data on client
        exp = "RESENDING: %s" % data
        self.failif(exp in client_res.stdout, "Data '%s' sent from server "
                    "were not received on client:\n%s" % (exp, err_str))

    def cleanup(self):
        self.record_iptables('final')
        if self.sub_stuff.get('dd') is not None:
            self.logdebug('Recovering docker daemon to original state')
            docker_daemon.restart_service(self.sub_stuff['dd'])
        super(rm_link, self).cleanup()
