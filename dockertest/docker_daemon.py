"""
Docker Daemon interface helpers and utilities
"""

import httplib
import socket
import json
from output import wait_for_output
from autotest.client.shared import service
from autotest.client.shared import utils


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
                             % (value.status, value.reason, value.read())
                             )
        return json.loads(value.read())

    def version(self):
        """
        Return version information as a json object
        """

        return self.get_json("/version")

# TODO: Add tcp, and fd subclasses


# Group of utils for managing docker daemon service.


def start_docker_daemon(docker_path, docker_args):
    """
    Start new docker daemon with special args.
    """
    service.SpecificServiceManager("docker").stop()
    cmd = [docker_path]
    cmd += docker_args

    daemon_process = utils.AsyncJob(" ".join(cmd), close_fds=True)

    out_fn = lambda: daemon_process.get_stderr()
    ret = wait_for_output(out_fn, r"-job acceptconnections\(\) = OK \(0\)")
    return ret, daemon_process


def restart_docker_service(daemon_process=None):
    if daemon_process:
        daemon_process.wait_for(0)

    service.SpecificServiceManager("docker").start()
