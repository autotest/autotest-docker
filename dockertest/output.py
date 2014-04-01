"""
Handlers for command-line output processing, crash/panic detection, etc.
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import logging
import re

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


class OutputGoodBase(object):
    """
    Compare True if all methods ending in '_check' return True on stdout/stderr
    """

    #: Dict mapping of checker-name (method name) to pass/fail boolean result
    output_good = None

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
        self.ignore_error = ignore_error
        if skip is None:
            skip = []
        self.stdout_strip = cmdresult.stdout.strip()
        self.stderr_strip = cmdresult.stderr.strip()
        self.output_good = {}
        for checker in [name for name in dir(self) if name.endswith('_check')]:
            method = getattr(self, checker)
            if callable(method) and checker not in skip:
                self.output_good[checker] = self.check_outerr(method)
        # Not nonzero means One or more checkers returned False
        if not ignore_error and not self.__nonzero__():
            # Str representation will provide details
            raise xceptions.DockerOutputError(str(self))

    def __nonzero__(self):
        """
        Implement truth value testing and for the built-in operation bool()

        Represents "True" if all checker results are True
        """
        return False not in self.output_good.values()

    def check_outerr(self, checker):
        """
        Call checker, return logical AND of results

        :param checker: Function/Staticmethod to call
        """
        # Assume stderr more likely to represent "problem"
        stderr_result = checker(self.stderr_strip)
        stdout_result = checker(self.stdout_strip)
        # Both must be True
        return stdout_result and stderr_result

    def __str__(self):
        """
        Make results of individual checkers accessible in human-readable format.
        """
        passed = [chkr for (chkr, good) in self.output_good.items() if good]
        failed = [chkr for (chkr, good) in self.output_good.items()
                  if not good]
        command = self.cmdresult.command
        exit_code = self.cmdresult.exit_status
        if self:  # Boolean instance
            return ("Output checkers %s all passed for command %s with exit "
                    "code %d" % (passed, command, exit_code))
        else:
            logging.debug(self.cmdresult)
            return ("Output checkers %s passed, but %s failed for command %s "
                    "with exit code %d (see debug log for details)"
                    % (passed, failed, command, exit_code))


class OutputGood(OutputGoodBase):
    """
    Compare True if no 'Go Panic' or 'Docker Usage' matches **not** found
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
