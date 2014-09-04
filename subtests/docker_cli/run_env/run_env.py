"""
This test checks function of `docker run -e VARIABLE=VALUE ...`
"""
import ast
import os
import random
import re
import time

from autotest.client import utils
from dockertest import config, xceptions
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd, AsyncDockerCmd
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtestCaller, SubSubtest


# requires: container, port, data
PYTHON_CLIENT = """import socket
import os
print "ENVIRON = " + str(os.environ)
addr = os.environ['%(container)s_PORT_%(port)s_TCP_ADDR']
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((addr, %(port)s))
sock.send("%(data)s")
print sock.recv(1024)
sock.close()

exit()
"""

# requires: port
PYTHON_SERVER = """import socket
import os
print "ENVIRON = " + str(os.environ)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("", %(port)s))
sock.listen(True)
conn, addr = sock.accept()
print "Connected by", addr
while True:
    data = conn.recv(1024)
    print "RECEIVED: " + data
    if not data:
        break
    conn.send("RESENDING: " + data)

conn.close()

exit()
"""


# FIXME: Remove this when BZ1131592 is resolved
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


class run_env(SubSubtestCaller):

    """ Subtest caller """


class run_env_base(SubSubtest):

    """ Base class """

    def _init_container(self, prefix, subargs, cmd):
        """
        Prepares dkrcmd and stores the name in self.sub_stuff['containers']
        :return: tuple(dkrcmd, name)
        """
        name = self.sub_stuff['dc'].get_unique_name(prefix, length=4)
        subargs.append("--name %s" % name)
        self.sub_stuff['containers'].append(name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append('bash -c')
        subargs.append(cmd)
        dkrcmd = InteractiveAsyncDockerCmd(self, 'run', subargs, verbose=False)
        return dkrcmd, name

    def initialize(self):
        super(run_env_base, self).initialize()
        # Prepare a container
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self.parent_subtest)
        self.sub_stuff['containers'] = []

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

    def cleanup(self):
        super(run_env_base, self).cleanup()
        self._cleanup_containers()


class port(run_env_base):

    """
    1. Starts server with custom -e ENV_VARIABLE=$RANDOM_STRING and opened port
    2. Starts client linked to server with another ENV_VARIABLE
    3. Booth prints the env as {}
    4. Client sends data to server (addr from env SERVER_PORT_$PORT_TCP_ADDR)
    5. Server prints data with prefix and resends them back with another one.
    6. Client prints the received data and finishes.
    7. Checks if env and all data were printed correctly.
    """

    def initialize(self):
        super(port, self).initialize()
        self.sub_stuff['server_env'] = utils.generate_random_string(8)
        params = {'port': random.randrange(4000, 5000),
                  'container': 'SERVER',
                  'data': ('Testing data %s'
                           % utils.generate_random_string(12))}
        self.sub_stuff['client_params'] = params
        self.sub_stuff['client_env'] = utils.generate_random_string(6)

    def run_once(self):
        super(port, self).run_once()
        params = self.sub_stuff['client_params']
        # start server
        subargs = ['-i', '-t', '-p %s' % params['port'],
                   '-e ENV_VARIABLE=%s' % self.sub_stuff['server_env']]

        servercmd, server = self._init_container('server', subargs, 'python')
        servercmd.execute(PYTHON_SERVER % params)

        # FIXME: Need to use ID instead of name, because docker-autotest can't
        # handle linked containers as the names are also listed, eg:
        # server_cuP0 => client_qYjF/server,server_cuP0
        for _ in xrange(100):
            cont = self.sub_stuff['dc'].list_containers_with_name(server)
            if len(cont) == 1:
                serverid = cont[0].long_id
                self.sub_stuff['containers'].append(serverid)
                break
            time.sleep(0.1)
        else:
            self.failif(True, "Container '%s' didn't started in 10s" % server)

        # start client
        subargs = ['-i', '-t', '--link %s:server' % server,
                   '-e ENV_VARIABLE=%s' % self.sub_stuff['client_env']]
        clientcmd, client = self._init_container('client', subargs, 'python')
        self.sub_stuff['client_name'] = client
        clientcmd.execute(PYTHON_CLIENT % params)

        # We can't wait for the process to finish, because currently it waits
        # until stdin is closed :-(
        for _ in xrange(100):
            conts = self.sub_stuff['dc'].list_containers_with_cid(serverid)
            if (len(conts) == 1 and conts[0].status
                    and "Exited" in conts[0].status):
                break   # Container finished, proceed to results
            time.sleep(0.1)
        else:
            self.failif(True, "Container '%s' didn't finish in 10s" % client)

        clientcmd.close()
        servercmd.close()

        self.sub_stuff['client_result'] = clientcmd.wait(1)
        self.sub_stuff['server_result'] = servercmd.wait(1)

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

    def postprocess(self):
        def get_env(output):
            for line in output.splitlines():
                if line.startswith('ENVIRON = {'):
                    return ast.literal_eval(line[10:])
            self.failif(True, "Fail to get env from output\n%s" % output)

        super(port, self).postprocess()
        client_res = self.sub_stuff['client_result']
        server_res = self.sub_stuff['server_result']
        err_str = "\n\nServer\n%s\n\nClient\n%s" % (server_res, client_res)
        # server env
        server_env = get_env(server_res.stdout)
        self.check_env(self.sub_stuff['server_env'], 'ENV_VARIABLE',
                       server_env, 'server', err_str)

        # client env
        client_env = get_env(client_res.stdout)
        self.check_env(self.sub_stuff['client_env'], 'ENV_VARIABLE',
                       client_env, 'client', err_str)
        # linked client env
        self.check_env("/%s/server" % self.sub_stuff['client_name'],
                       'SERVER_NAME', client_env, 'client', err_str)
        self.check_env(self.sub_stuff['server_env'], 'SERVER_ENV_ENV_VARIABLE',
                       client_env, 'client', err_str)
        addr = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        serv_port = str(self.sub_stuff['client_params']['port'])
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
        data = self.sub_stuff['client_params']['data']
        exp = "RECEIVED: %s" % data
        self.failif(exp not in server_res.stdout, "Data '%s' sent from client "
                    "were not received on server:\n%s" % (exp, err_str))
        # data on client
        exp = "RESENDING: %s" % data
        self.failif(exp not in client_res.stdout, "Data '%s' sent from server "
                    "were not received on client:\n%s" % (exp, err_str))
