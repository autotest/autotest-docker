"""
Handlers for command-line output processing, crash/panic detection, etc.
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import warnings
import re

import xceptions
from environment import AllGoodBase

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


class OutputGoodBase(AllGoodBase):
    """
    Compare True if all methods ending in '_check' return True on stdout/stderr
    """

    #: Reference to original CmdResult instance
    cmdresult = None

    #: Stripped standard-output string
    stdout_strip = None

    #: Stripped standard-error string
    stderr_strip = None

    def __init__(self, cmdresult, ignore_error=False, skip=None):
        """
        Run checks, define result attrs or raise xceptions.DockerOutputError

        :param cmdresult: autotest.client.utils.CmdResult instance
        :param ignore_error: Raise exceptions.DockerOutputError if False
        :param skip: Iterable of checks to bypass, None to run all
        """
        self.cmdresult = cmdresult
        self.stdout_strip = cmdresult.stdout.strip()
        self.stderr_strip = cmdresult.stderr.strip()
        # All methods called twice with mangled names, mangle skips also
        if skip is not None:
            newskip = []
            for checker in skip:
                newskip.append(checker + '_stdout')
                newskip.append(checker + '_stderr')
        else:
            newskip = skip
        self.__instattrs__(newskip)
        for checker in [name for name in dir(self) if name.endswith('_check')]:
            method = getattr(self, checker)
            self.callables[checker + '_stdout'] = getattr(self, checker)
            self.callables[checker + '_stderr'] = getattr(self, checker)
        self.call_callables()
        # Not nonzero means One or more checkers returned False
        if not ignore_error and not self.__nonzero__():
            # Str representation will provide details
            raise xceptions.DockerOutputError(str(self))

    def callable_args(self, name):
        if name.endswith('_stdout'):
            return {'output':self.stdout_strip}
        elif name.endswith('_stderr'):
            return {'output':self.stderr_strip}
        else:
            raise RuntimeError("Unexpected check method name %s" % name)

    # FIXME: Deprecate self.output_good in Major/Minor release
    @property
    def output_good(self):
        """
        Deprecated, do not use!
        """
        warnings.warn(PendingDeprecationWarning())
        # Make sure PrepareResults gets called
        self.__nonzero__()
        og = {}
        for key, value in self.results.items():
            basekey = key.replace('_stdout', '')
            basekey = basekey.replace('_stderr', '')
            # Represent result as logical and of both stdout/stderr values
            if basekey in og:
                og[basekey] = og[basekey] and value
            else:
                og[basekey] = value
        return og

class OutputGood(OutputGoodBase):
    """
    Container of standard checks
    """

    @staticmethod
    def crash_check(output):
        """
        Return False if Go panic string found in output

        :param output: Stripped output string
        :return: True if Go panic pattern **not** found
        """
        regex = re.compile(r'\s*panic:\s*.+error.*')
        for line in output.splitlines():
            if bool(regex.search(line.strip())):
                return False  # panic message found
        return True  # panic message not found

    @staticmethod
    def usage_check(output):
        """
        Return False if 'Docker usage' pattern found in output

        :param output: Stripped output string
        :return: True if usage message pattern **not** found
        """
        regex = re.compile(r'\s*usage:\s+docker\s+.*', re.IGNORECASE)
        for line in output.splitlines():
            if bool(regex.search(line.strip())):
                return False  # usage message found
        return True  # usage message not found

    @staticmethod
    def error_check(output):
        """
        Return False if 'Error: ' pattern found in output

        :param output: Stripped output string
        :return: True if 'Error: ' does **not** sppear
        """
        for line in output.splitlines():
            if line.lower().strip().count('error: '):
                return False
        return True

    #TODO: Other checks?
