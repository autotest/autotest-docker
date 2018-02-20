"""
Docker Daemon interface helpers and utilities
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import httplib
import logging
import socket
import json
import re
from autotest.client import utils


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


def which_docker():
    """
    Returns the name of the currently-running docker systemd service,
    as a string. This is usually 'docker' but could be 'docker-latest'
    or the name of a known docker-as-system-container service.
    """
    docker = 'docker'
    return 'podman'          # FIXME FIXME FIXME

    # Known docker-daemon services as of July 2017
    docker_services = ('docker', 'docker-latest', 'container-engine')

    # List systemd units, look for "xx.service loaded active running"
    re_svc = re.compile(r'^([\w-]+)\.service\s+loaded\s+active\s+running\s')
    list_units = 'systemctl list-units --full --type=service --state=running'
    units = utils.run(list_units).stdout.strip().splitlines()
    for line in units:
        found_running = re.match(re_svc, line)
        if found_running:
            unit = found_running.group(1)
            if unit in docker_services:
                docker = unit
    return docker


def systemd_action(action):
    """ Run the given systemctl action on the current docker service """
    return utils.run("systemctl %s %s.service" % (action, which_docker()))


def stop():
    """ stop the docker daemon """
    return systemd_action('stop')


def start():
    """ start the docker daemon """
    return systemd_action('start')


def restart():
    """ restart the docker daemon """
    return systemd_action('restart')


def systemd_show(prop):
    """
    Runs 'systemctl show --property=ARG' for given arg.
    Returns the value as a string.
    """
    cmd_result = systemd_action('show --property=%s' % prop)
    stdout = cmd_result.stdout
    if not stdout.startswith(prop + '='):
        raise RuntimeError("Unexpected output from %s: expected %s=XXXX,"
                           " got '%s'" % (cmd_result.command, prop, stdout))
    return stdout[(len(prop) + 1):].strip()


def pid():
    """ returns the process ID of currently-running docker daemon """
    mainpid = int(systemd_show('MainPID'))
    # systemd returns 0 for unknown or non-running units; this is
    # expected when testing podman, which has no daemon.
    if mainpid == 0:
        return 0
    cmd = cmdline(mainpid)
    if 'dockerd' in cmd[0]:
        return mainpid
    # As of April 2017 we may be running dockerd under runc. If so, actual
    # dockerd process is an immediate child of the one returned by systemd.
    for child_pid in utils.run("pgrep -P %s" % mainpid).stdout.split():
        cmd = cmdline(child_pid)
        if 'dockerd' in cmd[0]:
            return int(child_pid)
    # Urp. No dockerd process found. Cross fingers & hope systemd is right.
    logging.warning("docker_daemon.pid(): systemd reports %d,"
                    " which does not appear to be dockerd, but no child"
                    " processes appear to be dockerd either.", mainpid)
    return mainpid


def cmdline(process_id=None):
    """
    Returns the command line (argv) for the given process_id, as obtained
    from 'ps'. We don't use 'systemctl show' because that includes
    unexpanded variables. Return value is a list of strings.

    :param process_id: PID whose commandline we read (default: docker daemon)
    """
    if process_id is None:
        process_id = pid()
    # daemon won't be running if we're testing podman
    if int(process_id) == 0:
        return ''
    ps_command = 'ps -o command= -p %d' % int(process_id)
    return utils.run(ps_command).stdout.strip().split()


def user_namespaces_enabled():
    """ Returns true if docker daemon is running with user namespaces """
    return '--userns-remap=default' in cmdline()


def user_namespaces_uid():
    """ Returns the subordinate UID used for docker processes. """
    return _user_namespaces_id('/etc/subuid')


def user_namespaces_gid():
    """ Returns the subordinate GID used for docker processes. """
    return _user_namespaces_id('/etc/subgid')


def _user_namespaces_id(idfile):
    """
    Reads the given file (/etc/subuid or subgid), looks for a
    line of the form 'dockremap:XXXX:YYYY', returns XXXX.
    """
    with open(idfile, 'r') as subxid:
        for line in subxid:
            try:
                (login, xid, _) = line.split(':')
                if login == 'dockremap':
                    return int(xid)
            except ValueError:
                pass
    raise RuntimeError("User namespaces enabled, but"
                       " did not find 'dockremap' in %s" % idfile)
