"""
Docker Daemon interface helpers and utilities
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import httplib
import logging
import socket
import json
import os
import re
from autotest.client import utils

# File extension used for preserving original docker config file
PRESERVED_EXTENSION = '.docker-autotest-preserved'


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


def _systemd_action(action):
    return utils.run("systemctl %s %s.service" % (action, which_docker()))


def stop():
    """ stop the docker daemon """
    return _systemd_action('stop')


def start():
    """ start the docker daemon """
    return _systemd_action('start')


def restart():
    """ restart the docker daemon """
    return _systemd_action('restart')


def pid():
    """ returns the process ID of currently-running docker daemon """
    cmd_result = _systemd_action('show --property=MainPID')
    stdout = cmd_result.stdout
    if not stdout.startswith('MainPID='):
        raise RuntimeError("Unexpected output from %s: expected MainPID=NNN,"
                           " got '%s'" % (cmd_result.command, stdout))
    mainpid = int(stdout[8:])
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
    Returns the command line (argv) for the given process_id, as read
    from /proc/<pid>/cmdline. We don't use 'systemctl show' because
    that includes unexpanded variables. Return value is a list of strings.

    :param process_id: PID whose commandline we read (default: docker daemon)
    """
    if process_id is None:
        process_id = pid()
    cmdline_file = os.path.join('/proc', str(process_id), 'cmdline')
    with open(cmdline_file, 'r') as cmdline_fh:
        return cmdline_fh.read().split('\0')


def assert_pristine_environment():
    """
    Barf if there are any leftover .docker-autotest-preserved files
    in /etc/sysconfig; this would indicate that a previous test
    failed to clean up properly, and our system is in an
    undefined state.
    """
    for suffix in ['', '-latest']:
        path = '/etc/sysconfig/docker%s%s' % (suffix, PRESERVED_EXTENSION)
        if os.path.exists(path):
            raise RuntimeError("Leftover backup file: %s. System is"
                               " in undefined state! Please examine that"
                               " and its original file; if appropriate,"
                               " mv it back into place." % path)


def edit_options_file(remove=None, add=None):
    """
    Write a new /etc/sysconfig/docker* file with new OPTIONS string.
    Preserve the original.

    :param remove: string or list of strings - option(s) to remove from line
    :param add: string or list of strings - option(s) to add to line
    """
    sysconfig_file = '/etc/sysconfig/%s' % which_docker()
    sysconfig_bkp = sysconfig_file + PRESERVED_EXTENSION
    if os.path.exists(sysconfig_bkp):
        raise RuntimeError("Backup file already exists: %s" % sysconfig_bkp)
    sysconfig_tmp = sysconfig_file + '.tmp'
    with open(sysconfig_file, 'r') as sysconfig_fh_in:
        with open(sysconfig_tmp, 'w') as sysconfig_fh_out:
            for line in sysconfig_fh_in:
                if line.startswith('OPTIONS='):
                    line = edit_options_string(line, remove=remove, add=add)
                sysconfig_fh_out.write(line)
    os.link(sysconfig_file, sysconfig_bkp)
    os.rename(sysconfig_tmp, sysconfig_file)


def edit_options_string(line, remove=None, add=None):
    """
    Helper for edit_options_file(). Given an OPTIONS='...' string,
    returns OPTIONS='...' with the given options removed and/or added
    and a trailing newline.

    :param line: string of the form OPTIONS='something'
    :param remove: string or list of strings - option(s) to remove from line
    :param add: string or list of strings - option(s) to add to line
    """
    if not line.startswith('OPTIONS='):
        raise ValueError("input line does not start with OPTIONS= : %s" % line)
    line = line[8:].rstrip()
    quote = ''
    if line[0] == '"' or line[0] == "'":
        quote = line[0]
        if line[-1] != quote:
            raise ValueError("mismatched quotes in %s" % line)
        line = line[1:-1]
    if remove:
        removes = remove if isinstance(remove, list) else [remove]
        for remove_opt in removes:
            if remove_opt in line:
                line = line.replace(remove_opt, '')
    if add:
        adds = add if isinstance(add, list) else [add]
        for add_opt in adds:
            if add_opt not in line:
                line = line + ' ' + add_opt
    return 'OPTIONS=%s%s%s\n' % (quote, line.strip(), quote)


def revert_options_file():
    """
    Revert back to preserved /etc/sysconfig/docker* file.

    This function is safe to invoke even if the preserved file doesn't
    exist; the only situation in which that makes sense is in a test's
    cleanup() method if test prep has failed before edit_options_file().

    Note that we automatically invoke restart(): there is no possible
    situation in which it makes sense to revert options without restarting
    docker daemon.
    """
    sysconfig_file = '/etc/sysconfig/%s' % which_docker()
    sysconfig_bkp = sysconfig_file + PRESERVED_EXTENSION
    if os.path.exists(sysconfig_bkp):
        os.rename(sysconfig_bkp, sysconfig_file)
        restart()
