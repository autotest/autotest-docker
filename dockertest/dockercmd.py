"""
Frequently used docker CLI operations/data
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

from autotest.client import utils
from autotest.client.shared import error
from subtest import Subtest
from xceptions import (DockerNotImplementedError, DockerCommandError,
                       DockerExecError, DockerRuntimeError, DockerTestError)


class DockerCmdBase(object):

    """
    Setup a call docker subcommand as if by CLI w/ subtest config integration
    Execute docker subcommand with arguments and a timeout.

    :param subtest: A subtest.Subtest (**NOT** a SubSubtest) subclass instance
    :param subcomd: A Subcommand or fully-formed option/argument string
    :param subargs: (optional) A list of strings containing additional
                    args to subcommand
    :param timeout: Seconds to wait before terminating docker command
                    None to use 'docker_timeout' config. option.
    :raises DockerTestError: on incorrect usage
    """

    #: Evaluates ``True`` after first time ``execute()`` method is called
    executed = 0

    #: A list of strings containing additional args to subcommand, or None
    subargs = None

    #: Override for ``docker_timeout`` configuration value
    timeout = None

    #: String of subcommand or fully-formed option/argument string
    subcmd = None

    #: Log additional debugging related messages
    verbose = None

    #: Cached copy of result object from most recent execute() call
    cmdresult = None

    def __init__(self, subtest, subcmd, subargs=None, timeout=None,
                 verbose=True):
        # Check for proper type of subargs
        if subargs is not None:
            if (not isinstance(subargs, list) or
                    isinstance(subargs, (str, unicode))):
                raise DockerTestError("Invalid argument type: %s,"
                                      " subargs must be a list of"
                                      " strings." % (subargs))
        # Prevent accidental test.test instance passing
        if not isinstance(subtest, Subtest):
            raise DockerTestError("%s is not a Subtest instance or "
                                  "subclass.", subtest.__class__.__name__)
        else:
            self.subtest = subtest
        self.subcmd = str(subcmd)
        if subargs is None:
            # Allow consecutive runs with modifications
            self.subargs = []
        else:
            # Allow consecutive runs with modifications
            self.subargs = list(subargs)
        if timeout is None:
            # Defined in [DEFAULTS] guaranteed to exist
            self.timeout = subtest.config['docker_timeout']
        else:
            # config() autoconverts otherwise catch non-float convertable
            self.timeout = float(timeout)
        self.verbose = verbose

    def __str__(self):
        """
        Return full command-line string (wrapps command property)
        """
        if self.cmdresult is not None:
            return str(self.cmdresult).replace('\n', ' ')
        else:
            return str(self.command)

    def execute(self, stdin):  # pylint: disable=R0201
        """
        Execute docker subcommand

        :param stdin: String or file-descriptor int supplying stdin data
        :raise DockerCommandError: on incorrect usage
        :raise DockerExecError: on command failure
        :return: A CmdResult instance
        """

        self.executed += 1
        # Keep pylint quiet
        del stdin
        # This is an abstract method
        raise DockerNotImplementedError

    # Impl. specific stubb, can't be a function
    def execute_calls(self):  # pylint: disable=R0201
        """
        Returns the number of times ``execute()`` has been called

        :raise DockerRuntimeError: if unsupported by subclass
        """

        raise DockerRuntimeError

    @property
    def docker_options(self):
        """
        String of docker args
        """

        # Defined in [DEFAULTS] guaranteed to exist
        return self.subtest.config['docker_options']

    @property
    def docker_command(self):
        """
        String of docker command path
        """

        # Defined in [DEFAULTS] guaranteed to exist
        return self.subtest.config['docker_path']

    @property
    def command(self):
        """
        String representation of command + subcommand + args
        """

        if len(self.subargs) > 0:
            return ("%s %s %s %s" % (self.docker_command,
                                     self.docker_options,
                                     self.subcmd,
                                     " ".join(self.subargs))).strip()
        else:  # Avoid adding extra spaces anywhere in or to command
            return ("%s %s %s" % (self.docker_command,
                                  self.docker_options,
                                  self.subcmd)).strip()


class DockerCmd(DockerCmdBase):

    """
    Setup a call docker subcommand as if by CLI w/ subtest config integration
    Execute docker subcommand with arguments and a timeout.
    """

    def execute(self, stdin=None):

        """
        Run docker command, ignore any non-zero exit code
        """

        if self.verbose:
            self.subtest.logdebug("Executing docker command: %s", self)
        self.executed += 1
        try:
            self.cmdresult = utils.run(self.command, timeout=self.timeout,
                             stdin=stdin, verbose=False,
                             ignore_status=True)
            return self.cmdresult
        # ignore_status=True : should not see CmdError
        except error.CmdError, detail:
            # Something internal must have gone wrong
            raise DockerCommandError(self.command, detail.result_obj)

    def execute_calls(self):
        return int(self.executed)


class NoFailDockerCmd(DockerCmd):

    """
    Setup a call docker subcommand as if by CLI w/ subtest config integration
    Execute docker subcommand with arguments and a timeout.
    """

    def execute(self, stdin=None):

        """
        Execute docker command, raising DockerCommandError if non-zero exit
        """

        if self.verbose:
            self.subtest.logdebug("Executing docker command: %s", self)
        self.executed += 1
        try:
            self.cmdresult = utils.run(self.command, timeout=self.timeout,
                             stdin=stdin, verbose=False,
                             ignore_status=False)
            return self.cmdresult
        # Prevent caller from needing to import this exception class
        except error.CmdError, detail:
            raise DockerExecError(str(detail.result_obj))


class MustFailDockerCmd(DockerCmd):

    """
    Setup a call docker subcommand as if by CLI w/ subtest config integration
    Execute docker subcommand with arguments and a timeout.
    """

    def execute(self, stdin=None):
        """
        Execute docker command, raise DockerExecError if **zero** exit code

        :param stdin: String or file-like containing standard input contents
        :raises DockerCommandError: on incorrect usage
        :raises DockerExecError: on if command returns zero exit code
        :return: A CmdResult instance
        """

        if self.verbose:
            self.subtest.logdebug("Executing docker command: %s", self)
        self.executed += 1
        try:
            self.cmdresult = utils.run(self.command, timeout=self.timeout,
                                  stdin=stdin, verbose=False,
                                  ignore_status=True)
        # Prevent caller from needing to import this exception class
        except error.CmdError, detail:
            raise DockerCommandError(str(detail.result_obj))
        if self.cmdresult.exit_status == 0:
            raise DockerExecError("Unexpected command success: %s"
                                  % str(self.cmdresult))
        else:
            return self.cmdresult


class AsyncDockerCmd(DockerCmdBase):

    """
    Execute docker command as asynchronous background process on ``execute()``
    Execute docker subcommand with arguments and a timeout.
    """

    #: Used internally by execute()
    _async_job = None

    def execute(self, stdin=None):
        """
        Start execution of asynchronous docker command
        """

        if self.verbose:
            self.subtest.logdebug("Executing docker command: %s", self)
        self._async_job = utils.AsyncJob(self.command, verbose=False,
                                         stdin=stdin, close_fds=True)
        self.update_result()
        return self.cmdresult

    def wait(self, timeout=None):
        """
        Return CmdResult after waiting for process to end or timeout

        :param timeout: Max time to wait, self.timeout if None
        :raises DockerTestError: on incorrect usage
        :return: Complete CmdResult instance
        """

        if timeout is None:
            timeout = self.timeout
        if self._async_job is not None:
            return self._async_job.wait_for(timeout)
        else:
            raise DockerTestError("Attempted to wait before execute() called.")

    def update_result(self):
        """
        Forces cache update of current stdout/stdin content to self.cmdresult
        """
        if self.executed:
            self.cmdresult = self._async_job.result
            if self.stdout:
                self.cmdresult.stdout = self.stdout
            if self.stderr:
                self.cmdresult.stdout = self.stderr
            # Returns None if still running
            self.cmdresult.exit_status = self._async_job.sp.poll()

    @property
    def done(self):
        """
        Return True if processes has ended

        :raises DockerTestError: on incorrect usage
        """

        if self._async_job is None:
            raise DockerTestError("Attempted to wait for done before execute()"
                                  " called.")
        return self._async_job.sp.poll() is not None

    @property
    def stdout(self):
        """
        Represent string of stdout so far

        :raises DockerTestError: on incorrect usage
        """

        if self._async_job is not None:
            return self._async_job.get_stdout()
        else:
            raise DockerTestError("Attempted to access stdout before execute()"
                                  " called.")

    @property
    def stderr(self):
        """
        Represent string of stderr output so far

        :raises DockerTestError: on incorrect usage
        """

        if self._async_job is not None:
            return self._async_job.get_stderr()
        else:
            raise DockerTestError("Attempted to access stderr before execute()"
                                  " called.")

    @property
    def process_id(self):
        """
        Return the process id of the backgtround job

        :raises DockerTestError: on incorrect usage
        """

        if self._async_job is not None:
            return self._async_job.sp.pid
        else:
            raise DockerTestError("Attempted to get pid before execute()"
                                  " called.")

    @property
    def exit_status(self):
        """
        Return exit status integer or None if process has not ended

        :raises DockerTestError: on incorrect usage
        """

        if self._async_job is None:
            raise DockerTestError("Attempted to get exit status before "
                                  "execute() called.")
        return self._async_job.sp.returncode

    @property
    def executed(self):
        """
        Returns True if process was executed.
        """

        return self._async_job is not None
