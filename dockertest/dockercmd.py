
"""
Frequently used docker CLI operations/data
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import time
from autotest.client import utils
from subtest import SubBase
from xceptions import (DockerNotImplementedError,
                       DockerRuntimeError, DockerTestError)


class DockerCmdBase(object):

    """
    Call a docker subcommand as if by CLI w/ subtest config integration

    :param subtest: A subtest.SubBase or subclass instance
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

    #: Silence all logging messages
    quiet = False

    def __init__(self, subtest, subcmd, subargs=None, timeout=None,
                 verbose=True):
        self._cmdresult = None
        # Check for proper type of subargs
        if subargs is not None:
            if (not hasattr(subargs, '__iter__') or
                    isinstance(subargs, (str, unicode))):
                raise DockerTestError("Invalid argument type: %s,"
                                      " subargs must be an iterable of"
                                      " strings." % (subargs))
        # Only used for 'config' and 'logfoo' attributes
        if not isinstance(subtest, SubBase):
            raise DockerTestError("%s is not a SubBase instance."
                                  % subtest.__class__.__name__)
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

    @property
    def details(self):
        """
        Returns substitution dictionary for __str__ and logging.
        """

        # No problem including extra details in dict
        dct = {'exe': self.executed,
               'to': self.timeout,
               'suba': self.subargs,
               'subc': self.subcmd,
               'verb': self.verbose}

        if self.cmdresult is not None:
            # Don't assume executed command is current command
            dct['cmd'] = self.cmdresult.command
            dct['exit'] = self.exit_status  # pulls from self.cmdresult
            dct['out'] = self.stdout
            dct['err'] = self.stderr
            dct['dur'] = self.duration
        else:
            dct['cmd'] = self.command  # not yet executed
            dct['exit'] = None
            dct['out'] = None
            dct['err'] = None
            dct['dur'] = None
        return dct

    def __str__(self):
        """
        Return string representation of instance w/ details if verbose=True
        """

        # If command hasn't executed yet, can be really short string
        if not self.executed:
            fmt = "Command: %(cmd)s"
        else:
            # provide more details
            fmt = ("Command: %(cmd)s\n"
                   "Timeout: %(to)s\n"
                   "Executed: %(exe)s\n"
                   "Duration: %(dur)s\n"
                   "Exit code: %(exit)s\n"
                   # Make whitespace in output clearly visible
                   "Standard Out: \"\"\"%(out)s\"\"\"\n"
                   "Standard Error: \"\"\"%(err)s\"\"\"\n")
        return fmt % self.details

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
    def stdout(self):
        """
        Represent string of stdout

        :raises DockerTestError: on incorrect usage
        """

        if self.cmdresult is None:
            raise DockerTestError("Attempted to access stdout before execute()"
                                  " called.")
        return self.cmdresult.stdout

    @property
    def stderr(self):
        """
        Represent string of stderr

        :raises DockerTestError: on incorrect usage
        """

        if self.cmdresult is None:
            raise DockerTestError("Attempted to access stderr before execute()"
                                  " called.")
        return self.cmdresult.stderr

    @property
    def exit_status(self):
        """
        Represent exit code

        :raises DockerTestError: on incorrect usage
        """

        if self.cmdresult is None:
            raise DockerTestError("Attempted to access exit_code before "
                                  "execute() called.")
        else:
            return self.cmdresult.exit_status

    @property
    def duration(self):
        """
        Represent the duration / elapsed time of command

        :raises DockerTestError: on incorrect usage
        """

        if self.cmdresult is None:
            raise DockerTestError("Attempted to access duration before "
                                  "execute() called.")
        else:
            return self.cmdresult.duration

    # Treat result CmdResult as immutable for uniform behavior across subclass

    @property
    def cmdresult(self):
        """
        Represent fresh CmdResult value (not reference)
        """

        if self._cmdresult is None:
            self._cmdresult = utils.CmdResult(command=self.command)
        return self._cmdresult

    @cmdresult.setter
    def cmdresult(self, value):
        """
        Allow subclasses ability to update the private cache attribute

        :param value:  New CmdResult instance to set (will be copied)
        """

        self._cmdresult = utils.CmdResult(command=value.command,
                                          stdout=value.stdout,
                                          stderr=value.stderr,
                                          exit_status=value.exit_status,
                                          duration=value.duration)
        return self.cmdresult

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
    def __init__(self, subtest, subcmd, subargs=None, timeout=None,
                 verbose=True):
        super(DockerCmd, self).__init__(subtest, subcmd, subargs,
                                        timeout, verbose)

    def execute(self, stdin=None):
        """
        Run docker command, ignore any non-zero exit code
        """

        if not self.quiet:
            if isinstance(stdin, basestring):   # stringg
                str_stdin = "  <<< %r" % stdin
            elif isinstance(stdin, int):        # pipe
                str_stdin = "  <<< PIPE: %s" % stdin
            elif stdin:                         # file-like object
                str_stdin = "  <<< %s" % stdin
            else:                               # Nothing
                str_stdin = ""
            self.subtest.logdebug("Execute %s%s", self.command, str_stdin)
        self.cmdresult = utils.run(self.command, timeout=self.timeout,
                                   stdin=stdin, verbose=False,
                                   ignore_status=True)
        self.executed += 1
        if self.verbose:
            self.subtest.logdebug(str(self))
        # Return value, not reference
        return self.cmdresult

    def execute_calls(self):
        """
        Return the number of times ``execute()`` has been called
        """
        return self.executed


class AsyncDockerCmd(DockerCmdBase):

    """
    Execute docker command as asynchronous background process on ``execute()``
    Execute docker subcommand with arguments and a timeout.
    """
    #: Private, class assumes exclusive access and no locking is performed
    _async_job = None

    def __init__(self, subtest, subcmd, subargs=None, timeout=None,
                 verbose=True):
        super(AsyncDockerCmd, self).__init__(subtest, subcmd, subargs,
                                             timeout, verbose)

    def execute(self, stdin=None):
        """
        Start execution of asynchronous docker command
        """

        if self._async_job is not None:
            self.subtest.logwarning("Calling execute() before "
                                    "wait() on existing async job "
                                    "is very likely going to leak "
                                    "processes!!")
        if not self.quiet:
            if isinstance(stdin, basestring):
                str_stdin = "  <<< %r" % stdin
            elif isinstance(stdin, int):
                str_stdin = "  <<< PIPE: %s" % stdin
            elif stdin:
                str_stdin = "  <<< %s" % stdin
            else:
                str_stdin = ""
            self.subtest.logdebug("Async-execute: %s%s", str(self), str_stdin)
        self.executed += 1
        self._async_job = utils.AsyncJob(self.command, verbose=False,
                                         stdin=stdin, close_fds=True)
        return self.cmdresult

    def wait(self, timeout=None):
        """
        Return CmdResult after waiting for process to end or timeout

        :param timeout: Max time to wait, self.timeout if None
        :raises DockerTestError: on incorrect usage
        :return: Complete CmdResult instance
        """

        if self._async_job is None:
            raise DockerTestError("Attempted to wait before execute() called.")
        if timeout is None:
            timeout = self.timeout
        if self.verbose and not self.quiet:
            self.subtest.logdebug("Waiting %s for async-command to finish",
                                  timeout)
        self._async_job.wait_for(timeout)
        return self.cmdresult

    def update_result(self):
        """
        Deprecated, do not use

        :return: Up to date cmdresult value or None if not executed()
        """
        self.subtest.logwarning("AsyncDockerCmd.update_result() deprecated, "
                                "use cmdresult property instead.")

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
    def process_id(self):
        """
        Return the process id of the command

        :raises DockerTestError: on incorrect usage
        """

        if self._async_job is None:
            raise DockerTestError("Attempted to get pid before execute()"
                                  " called.")
        return self._async_job.sp.pid

    # Override base-class property methods to give up-to-second details

    @property
    def cmdresult(self):
        # FIXME: Can't seem to assign to parent-class property
        #        using private attribute instead, uggg.
        if self._async_job is None:
            self._cmdresult = utils.CmdResult(command=self.command)
        else:
            self._cmdresult = utils.CmdResult(command=self.command,
                                              stdout=self.stdout,
                                              stderr=self.stderr,
                                              exit_status=self.exit_status,
                                              duration=self.duration)
        return super(AsyncDockerCmd, self).cmdresult

    @property
    def stdout(self):
        if self._async_job is None:
            return None
        else:
            return self._async_job.get_stdout()

    @property
    def stderr(self):
        if self._async_job is None:
            return None
        else:
            return self._async_job.get_stderr()

    @property
    def exit_status(self):
        if self._async_job is None:
            return None
        else:
            return self._async_job.sp.poll()

    @property
    def duration(self):
        if self._async_job is None:
            return None
        if self._async_job.sp.poll() is not None:
            # Total elapsed time
            duration = self._async_job.result.duration
        else:
            # Current elapsed time
            duration = time.time() - self._async_job.start_time
        return duration
