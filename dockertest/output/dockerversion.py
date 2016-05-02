"""
Handlers for docker version parsing
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import re
from autotest.client import utils
import subprocess
from dockertest.xceptions import DockerOutputError, DockerTestNAError
from dockertest.version import LooseVersion


class DockerVersion(object):

    """
    Parser of docker-cli version command output as client/server properties

    :param version_string: Raw, possibly empty or multi-line output
                           from docker version command.
    """
    #: Raw, possibly empty or multi-line output from docker version command.
    #: Read-only, set in __init__
    version_string = None
    #: Various cache's for properties (do not use)
    _client = None
    _server = None
    _client_lines = None
    _server_lines = None
    _client_info = None
    _server_info = None
    _has_distinct_exit_codes = None

    def __init__(self, version_string=None, docker_path=None):
        # If called without an explicit version string, run docker to find out
        if version_string is None:
            if docker_path is None:
                docker_path = 'docker'
            version_string = subprocess.check_output(docker_path + ' version',
                                                     shell=True,
                                                     close_fds=True)
        self.version_string = version_string

    def _oops(self, what):
        raise DockerOutputError("Couldn't parse %s from %s" %
                                (what, self.version_string))

    # This is old code, not updating to preserve old behavior
    def _old_client(self):
        if self._client is None:
            regex = re.compile(r'Client\s+version:\s+(\d+\.\d+\.\d+\S*)',
                               re.IGNORECASE)
            mobj = None
            for line in self.version_lines:
                mobj = regex.search(line.strip())
                if bool(mobj):
                    self._client = mobj.group(1)
        if self._client is None:
            self._oops('client version')
        return self._client

    # This is old code, not updating to preserve old behavior
    def _old_server(self):
        if self._server is None:
            regex = re.compile(r'Server\s*version:\s*(\d+\.\d+\.\d+\S*)',
                               re.IGNORECASE)
            mobj = None
            for line in self.version_lines:
                mobj = regex.search(line.strip())
                if bool(mobj):
                    self._server = mobj.group(1)
        if self._server is None:
            self._oops('server version')
        return self._server

    def _split_client_server(self):
        # Split the raw string into client & server sections
        client_lines = []
        server_lines = []
        version_lines = list(self.version_lines)  # work on a copy
        version_lines.reverse()  # start at beginning
        while version_lines:
            version_line = version_lines.pop().strip()
            if version_line == '':
                continue
            elif version_line.find('Client:') > -1:
                # Don't assume which section came first
                while version_lines and version_lines[-1].find('Server:') < 0:
                    version_line = version_lines.pop().strip()
                    if version_line == '':
                        continue
                    client_lines.append(version_line)
                continue
            elif version_line.find('Server:') > -1:
                # Don't assume which section came first
                while version_lines and version_lines[-1].find('Client:') < 0:
                    version_line = version_lines.pop().strip()
                    if version_line == '':
                        continue
                    server_lines.append(version_line)
                continue
            else:
                msg = ("Unexpected line '%s' in version string: '%s'"
                       % (version_line, self.version_string))
                raise DockerOutputError(msg)
        return (client_lines, server_lines)

    # This is to preserve API behavior for old tests
    @property
    def version_lines(self):
        """Read-only property that returns all lines in version table"""
        return self.version_string.splitlines()

    @property
    def client_lines(self):
        """
        Read-only property of split/stripped client section of version string
        """
        if not self._client_lines:
            (self._client_lines,
             self._server_lines) = self._split_client_server()
        return self._client_lines

    @property
    def server_lines(self):
        """
        Read-only property of split/stripped server section of version string
        """
        if not self._server_lines:
            (self._client_lines,
             self._server_lines) = self._split_client_server()
        return self._server_lines

    def _info(self, is_client, key):
        key = key.strip()
        if is_client:
            infodict = self._client_info
            infolines = self.client_lines
        else:
            infodict = self._server_info
            infolines = self.server_lines
        try:
            return infodict[key.strip().lower()]
        except TypeError:  # infodict == None
            if is_client:
                self._client_info = {}
            else:
                self._server_info = {}
            return self._info(is_client, key)
        except KeyError:  # infodict == empty
            if not infodict:
                for line in infolines:
                    try:
                        _key, value = line.strip().lower().split(':', 1)
                    except ValueError:
                        raise ValueError("Error splitting info line '%s'"
                                         % line)
                    infodict[_key.strip()] = value.strip()
                return self._info(is_client, key)
            else:  # avoid infinite recursion
                self._oops("key %s" % key)

    def client_info(self, key):
        """Return item named 'key' from client section of version info table"""
        return self._info(True, key)

    def server_info(self, key):
        """Return item named 'key' from server section of version info table"""
        return self._info(False, key)

    @property
    def client(self):
        """
        Read-only property representing version-number string of docker client
        """
        if self._client is None:
            try:
                self._client = self._old_client()
            except DockerOutputError:
                self._client = self.client_info('version')
        if self._client is None:
            self._oops('client version')
        return self._client

    @property
    def server(self):
        """
        Read-only property representing version-number string of docker server
        """
        if self._server is None:
            try:
                self._server = self._old_server()
            except DockerOutputError:
                self._server = self.server_info('version')
        if self._server is None:
            self._oops('server version')
        return self._server

    @staticmethod
    def _require(wanted, name, other_version):
        required_version = LooseVersion(wanted)
        if other_version < required_version:
            msg = ("Test requires docker %s version >= %s; %s found"
                   % (name, required_version, other_version))
            raise DockerTestNAError(msg)
        # In case it's useful to caller
        return other_version

    def require_server(self, wanted):
        """
        Run 'docker version', parse server version, compare to wanted.

        :param wanted: required docker (possibly remote) server version
        :raises DockerTestNAError: installed docker < wanted
        """
        return self._require(wanted, 'server', self.server)

    def require_client(self, wanted):
        """
        Run 'docker version', parse client version, compare to wanted.

        :param wanted: required docker client version
        :raises DockerTestNAError: installed docker < wanted
        """
        return self._require(wanted, 'client', self.client)

    @property
    def has_distinct_exit_codes(self):
        """
        2016-03-23 **TEMPORARY** - for transition from docker-1.9 to 1.10

        docker-1.10 will introduce distinct exit codes to allow differentiating
        between container status and errors from docker run itself; see
        bz1097344 and docker PR14012. If we see an exit code of 125 here,
        assume we're using the new docker.
        """
        if self._has_distinct_exit_codes is None:
            try:
                # docker-1.10 *must* support distinct exit codes
                self.require_client('1.10')
                has = True
            except DockerTestNAError:
                # some builds of 1.9 might support it. (FIXME: really?)
                d_run = utils.run('docker run --invalid-opt invalid-image',
                                  ignore_status=True)
                has = (d_run.exit_status > 120)
            DockerVersion._has_distinct_exit_codes = has
        return DockerVersion._has_distinct_exit_codes
