"""
Docker Daemon interface helpers and utilities
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import httplib
import socket
import json
from autotest.client.shared import service
from autotest.client import utils
from output import wait_for_output


class ClientBase(object):

    """
    Represents a connection with a single interface to Docker Daemon

    :param uri:  URI understood handled by interface
    """

    #: Interface class/instance to use
    interface = None

    def __init__(self, uri):
        self.uri = uri

    def get(self, resource):
        """
        Get interface-specific value using interface-specific methods.

        :param resource: Opaque value specific to interface.
        :return: Opaque value specific to interface.
        """

        raise NotImplementedError

    @staticmethod
    def value_to_json(value):
        """
        Process value returned by get() into a value_to_json object

        :param value: Opaque value returned by get().
        :raises ValueError: When value is invalid/unsupported
        :return: value_to_json opaque-object (impl. specific)
        """

        raise NotImplementedError

    def get_json(self, resource):
        """
        Process get(resource) result through value_to_json() method, return
        json object.
        """

        return self.value_to_json(self.get(resource))


class SocketClient(ClientBase):

    """
    Connection to docker daemon through a unix socket
    """

    class UHTTPConnection(httplib.HTTPConnection):

        """
        Subclass of Python library HTTPConnection that uses a unix-domain
        socket

        :param path: Path to the existing unix socket
        """

        # Too few pub. meth: Subclass of builtin, don't break design.
        # pylint: disable=R0903

        def __init__(self, path="/var/run/docker.sock"):
            httplib.HTTPConnection.__init__(self, 'localhost')
            self.path = path

        def connect(self):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.path)
            self.sock = sock

    interface = UHTTPConnection

    def __init__(self, uri="/var/run/docker.sock"):
        super(SocketClient, self).__init__(uri)
        self._connection = self.interface(uri)

    def get(self, resource):
        self._connection.request("GET", resource)
        return self._connection.getresponse()  # httplib.HTTPResponse

    @staticmethod
    def value_to_json(value):
        if value.status != 200:
            raise ValueError("Bad response status %s (%s)\nRaw data: %s"
                             % (value.status, value.reason, value.read()))
        return json.loads(value.read())

    def version(self):
        """
        Return version information as a json object
        """

        return self.get_json("/version")

# Group of utils for managing docker daemon service.


def start(docker_path, docker_args):
    """
    Start new docker daemon with special args.

    :param docker_path: Full path to executable
    :param docker_args: List of string of command-line arguments to pass
    :returns: Opaque daemon_process object (not for direct use)
    """
    # _SpecificServiceManager creates it's methods during __init__()
    if service.get_name_of_init() == "systemd":
        # pylint: disable=E1101
        utils.run("systemctl stop docker.socket", ignore_status=True)
    service.SpecificServiceManager("docker").stop()  # pylint: disable=E1101
    cmd = [docker_path]
    cmd += docker_args

    daemon_process = utils.AsyncJob(" ".join(cmd), close_fds=True)
    return daemon_process


def output_match(daemon_process,
                 timeout=120,
                 regex=r"-job acceptconnections\(\) = OK \(0\)"):
    """
    Return True if daemon_process output matches regex within timeout period

    :param daemon_process: Opaque daemon_process object (not for direct use)
    :param regex: Regular expression to search for
    :param timeout: Maximum time to wait before returning False
    """
    return wait_for_output(daemon_process.get_stderr,
                           regex,
                           timeout=timeout)


def restart_service(daemon_process=None):
    """
    Restart the docker service using host OS's service manager

    :param daemon_process: Opaque daemon_process object (not for direct use)
    """
    if daemon_process:
        daemon_process.kill_func()
        daemon_process.wait_for(10)
    # _SpecificServiceManager creates it's methods during __init__()
    if service.get_name_of_init() == "systemd":
        utils.run("systemctl start docker.socket", ignore_status=True)
    service.SpecificServiceManager("docker").start()  # pylint: disable=E1101
