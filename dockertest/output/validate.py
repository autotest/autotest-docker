"""
Handlers for command-line output processing, crash/panic detection, etc.
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import re
from autotest.client import utils
import subprocess
from dockertest.xceptions import DockerExecError, DockerOutputError
from . dockerversion import DockerVersion


class AllGoodBase(object):

    """
    Abstract class representing aggregate True/False value from callables
    """

    #: Mapping of callable name to instance
    callables = None

    #: Mapping of callable name to True/False value
    results = None

    #: Mapping of callable name to detailed results
    details = None

    #: Iterable of callable names to bypass
    skip = None

    def __init__(self, *args, **dargs):
        raise NotImplementedError()

    def __instattrs__(self, skip=None):
        """
        Override class variables with empty instance values

        :param skip: Iterable of callable names to not run
        """

        self.callables = {}
        self.results = {}
        self.details = {}
        if skip is None:
            self.skip = []
        else:
            self.skip = skip

    def __nonzero__(self):
        """
        Implement truth value testing and for the built-in operation bool()
        """

        return False not in self.results.values()

    def __str__(self):
        """
        Make results of individual checkers accessible in human-readable format
        """

        goods = [name for (name, result) in self.results.items() if result]
        bads = [name for (name, result) in self.results.items() if not result]
        if self:  # use self.__nonzero__()
            msg = "All Good: %s" % goods
        else:
            msg = "Good: %s; Not Good: %s; " % (goods, bads)
            msg += "Details:"
            dlst = [' (%s, %s)' % (name, self.detail_str(name))
                    for name in bads]
            msg += ';'.join(dlst)
        return msg

    def detail_str(self, name):
        """
        Convert details value for name into string

        :param name: Name possibly in details.keys()
        :return: String
        """

        return str(self.details.get(name, "No details"))

    #: Some subclasses need this to be a bound method
    def callable_args(self, name):  # pylint: disable=R0201
        """
        Return dictionary of arguments to pass through to each callable

        :param name: Name of callable to return args for
        :return: Dictionary of arguments
        """

        del name  # keep pylint happy
        return dict()

    def call_callables(self):
        """
        Call all instances in callables not in skip, storing results
        """

        _results = {}
        for name, call in self.callables.items():
            if callable(call) and name not in self.skip:
                _results[name] = call(**self.callable_args(name))
        self.results.update(self.prepare_results(_results))

    #: Some subclasses need this to be a bound method
    def prepare_results(self, results):  # pylint: disable=R0201
        """
        Called to process results into instance results and details attributes

        :param results: Dict-like of output from callables, keyed by name
        :returns: Dict-like for assignment to instance results attribute.
        """

        # In case call_callables() overridden but this method is not
        return dict(results)


class OutputGoodBase(AllGoodBase):

    """
    Compare True if all methods ending in '_check' return True on stdout/stderr

    :param cmdresult: autotest.client.utils.CmdResult instance
    :param ignore_error: Raise xceptions.DockerOutputError if False
    :param skip: Iterable of checks to bypass, None to run all
    """

    #: Reference to original CmdResult instance
    cmdresult = None

    #: Stripped standard-output string
    stdout_strip = None

    #: Stripped standard-error string
    stderr_strip = None

    def __init__(self, cmdresult, ignore_error=False, skip=None):
        # Base class __init__ is abstract
        # pylint: disable=W0231
        self.cmdresult = cmdresult
        self.stdout_strip = cmdresult.stdout.strip()
        self.stderr_strip = cmdresult.stderr.strip()
        # All methods called twice with mangled names, mangle skips also
        if skip is not None:
            if isinstance(skip, (str, unicode)):
                skip = [skip]
            newskip = []
            for checker in skip:
                newskip.append(checker + '_stdout')
                newskip.append(checker + '_stderr')
        else:
            newskip = skip
        self.__instattrs__(newskip)
        for checker in [name for name in dir(self) if name.endswith('_check')]:
            self.callables[checker + '_stdout'] = getattr(self, checker)
            self.callables[checker + '_stderr'] = getattr(self, checker)
        self.call_callables()
        # Not nonzero means One or more checkers returned False
        if not ignore_error and not self.__nonzero__():
            # Str representation will provide details
            raise DockerOutputError(str(self))

    def __str__(self):
        if not self.__nonzero__():
            msg = super(OutputGoodBase, self).__str__()
            return "%s\nSTDOUT:\n%s\nSTDERR:\n%s" % (msg, self.stdout_strip,
                                                     self.stderr_strip)
        else:
            return super(OutputGoodBase, self).__str__()

    def callable_args(self, name):
        if name.endswith('_stdout'):
            return {'output': self.stdout_strip}
        elif name.endswith('_stderr'):
            return {'output': self.stderr_strip}
        else:
            raise RuntimeError("Unexpected check method name %s" % name)

    def prepare_results(self, results):
        duplicate = False
        for checker, passed in results.items():
            if not passed and not duplicate:
                exit_status = self.cmdresult.exit_status
                stdout = self.cmdresult.stdout.strip()
                stderr = self.cmdresult.stderr.strip()
                detail = 'Command '
                if exit_status != 0:
                    detail += 'exit %d ' % exit_status
                if len(stdout) > 0:
                    detail += 'stdout "%s" ' % stdout
                if len(stderr) > 0:
                    detail += 'stderr "%s".' % stderr
                self.details[checker] = detail
                duplicate = True  # all other failures will be same
        return super(OutputGoodBase, self).prepare_results(results)


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
            return line.lower().strip().find('error') == -1
        return True

    @staticmethod
    def fata_check(output):
        """
        Return False if 'FATA[xxxx]' pattern found in output

        :param output: Stripped output string
        :return: True if 'FATA ' does **not** sppear
        """
        regex = re.compile(r'FATA\[\d+')
        return not bool(regex.search(output))


class OutputNotBad(OutputGood):

    """
    Same as OutputGood, except skip checking error/usage messages by default
    """

    #: Full command line that outputs string to search for kernel oopses
    GET_PANIC_CMD = ('journalctl --no-pager --all --reverse '
                     '--dmesg --boot --priority=warning')

    #: Kernel oops string to look for
    OOPS_STRING = 'oops'

    #: Caches output value from running GET_PANIC_CMD, None if Error
    _dmesg_cache = None

    def __init__(self, cmdresult, ignore_error=False, skip=None):
        defaults = ['error_check', 'usage_check']
        if skip is None:
            skip = defaults
        else:
            if isinstance(skip, basestring):
                skip = defaults + [skip]
            else:
                skip = defaults + skip
        super(OutputNotBad, self).__init__(cmdresult, ignore_error, skip)

    def kernel_panic(self, output):
        """
        Checks output from ``GET_PANIC_CMD`` for ``OOPS_STRING``
        """
        del output  # not used
        return self.dmesg.lower().strip().find(self.OOPS_STRING) == -1

    @property
    def dmesg(self):
        """
        Represents (cached) ``GET_PANIC_CMD`` output last obtained.
        """
        if self._dmesg_cache is None:
            self._dmesg_cache = subprocess.check_output(self.GET_PANIC_CMD,
                                                        shell=True)
        return self._dmesg_cache


def wait_for_output(output_fn, pattern, timeout=60, timestep=0.2):
    r"""
    Wait for matched_string in async_process.stdout max for time==timeout.

    :param process_output_fn: function which returns data for matching.
    :type process_output_fn: function
    :param pattern: string which should be found in stdout.
    :return: True if pattern matches process_output else False
    """
    if not callable(output_fn):
        raise TypeError("Output function type %s value %s is not a callable"
                        % (output_fn.__class__.__name__, str(output_fn)))
    regex = re.compile(pattern)
    _fn = lambda: regex.findall(output_fn()) != []
    res = utils.wait_for(_fn, timeout, step=timestep)
    if res:
        return True
    return False


def mustpass(cmdresult, failmsg=None):
    """
    Check docker cmd results for pass. Raise exception when command failed.

    :param cmdresult: results of cmd.
    :type cmdresult: object convertible to string with variable exit_status
    :param failmsg: Additional messages for describing problem when cmd fails.
    """
    if failmsg is None:
        details = "%s" % cmdresult
    else:
        details = "%s\n%s" % (failmsg, cmdresult)
    OutputNotBad(cmdresult)
    if cmdresult.exit_status != 0:
        raise DockerExecError("Unexpected non-zero exit code, details: %s"
                              % details)
    return cmdresult


def mustfail(cmdresult, expected_status=None, failmsg=None):
    """
    Check docker cmd results for pass. Raise exception when command passed.

    :param cmdresult: results of cmd.
    :type cmdresult: object convertible to string with variable exit_status
    :param expected_status: exit status we expect to see from cmd.
                            NOTE: for backward compatibility with pre-20160331
                            code, we try to gracefully handle if this param
                            is missing (default to 1) or a string (set failmsg)
    :type expected_status: integer, 1-255
    :param failmsg: Additional messages for describing problem when cmd fails.
    """
    # FIXME: temporary: backward compatibility for pre-20160330 code
    # FIXME: remove before the next API-changing release
    if expected_status is None:                    # old: mustfail(x)
        expected_status = 1
    if isinstance(expected_status, basestring):    # old: mustfail(x, "msg")
        if not expected_status.isdigit():     # pylint: disable=E1101
            failmsg = expected_status
            expected_status = 1

    if failmsg is None:
        details = "%s" % cmdresult
    else:
        details = "%s\n%s" % (failmsg, cmdresult)
    OutputNotBad(cmdresult)
    if cmdresult.exit_status == expected_status:
        return cmdresult
    # On pre-1.10 docker, accept any nonzero exit status: it's impossible
    # to automatically map docker-1.10 codes to 1.9
    # FIXME: temporary; remove once we no longer run on pre-1.10 docker
    if not DockerVersion().has_distinct_exit_codes:
        if cmdresult.exit_status != 0:
            return cmdresult

    raise DockerExecError("Unexpected exit code %d; expected %d. Details: %s"
                          % (cmdresult.exit_status, expected_status, details))
