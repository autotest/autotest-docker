"""
Handlers for command-line output processing, crash/panic detection, etc.
"""

import re, logging
import xceptions

class DockerVersion(object):
    """
    Parser of docker-cli version command output as client/server properties
    """
    #: Raw, possibly empty or multi-line output from docker version command.
    #: Read-only, set in __init__
    version_string = None
    #: Line-split version of version_string, not stripped, read-only, set in
    #: __init__
    version_lines = None
    _client = None
    _server = None
    # TODO: Add *_go & *_git versions?

    def __init__(self, version_string):
        """
        Initialize version command output parser instance

        :param version_string: Raw, possibly empty or multi-line output
                               from docker version command.
        """
        self.version_string = version_string
        self.version_lines = self.version_string.splitlines()

    @property
    def client(self):
        """
        Read-only property representing version-number string of docker client
        """
        if self._client is None:
            regex = re.compile(r'Client\s+version:\s+(\d+\.\d+\.\d+)',
                               re.IGNORECASE)
            mobj = None
            for line in self.version_lines:
                mobj = regex.search(line.strip())
                if bool(mobj):
                    self._client = mobj.group(1)
        if self._client is None:
            raise xceptions.DockerOutputError("Couldn't parse client version "
                                              "from %s" % self.version_string)
        return self._client

    @property
    def server(self):
        """
        Read-only property representing version-number string of docker server
        """
        if self._server is None:
            regex = re.compile(r'Server\s*version:\s*(\d+\.\d+\.\d+)',
                               re.IGNORECASE)
            mobj = None
            for line in self.version_lines:
                mobj = regex.search(line.strip())
                if bool(mobj):
                    self._server = mobj.group(1)
        if self._server is None:
            raise xceptions.DockerOutputError("Couldn't parse server version "
                                              "from %s" % self.version_string)
        return self._server

def crash_check(output):
    """
    Raise DockerOutputError if 'panic' string found in output

    :param output: Raw output from a docker CLI command
    """
    regex = re.compile(r'\s*panic:\s*.+error.*')
    for line in output.splitlines():
        if bool(regex.search(line.strip())):
            logging.debug('Command output:\n%s\n', output)
            raise xceptions.DockerOutputError("Docker command crash detected "
                                              "(see debug log for output)")

def usage_check(output):
    """
    Raise DockerOutputError if 'usage' string found in output

    :param output: Raw output from a docker CLI command
    """
    regex = re.compile(r'\s*usage:\s+docker\s+.*', re.IGNORECASE)
    for line in output.splitlines():
        if bool(regex.search(line.strip())):
            logging.debug('Command output:\n%s\n', output)
            raise xceptions.DockerOutputError("Docker command usage help "
                                              "detected (see debug log for "
                                              "output)")
