
"""
Frequently used docker CLI operations/data
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import time
from autotest.client import utils
from subtestbase import SubBase
from xceptions import DockerNotImplementedError
from xceptions import DockerExecError, DockerTestError
from xceptions import DockerCommandError


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
            self.subargs = [arg.strip()
                            for arg in subargs
                            if arg is not None or arg is not '']
        if timeout is None:
            # Defined in [DEFAULTS] guaranteed to exist
            self.timeout = float(subtest.config['docker_timeout'])
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
        dct = {'to': self.timeout,
               'suba': self.subargs,
               'subc': self.subcmd,
               'verb': self.verbose}

        if self.cmdresult is not None:
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
        if self.cmdresult is None:
            fmt = "Command: %(cmd)s"
        else:
            # provide more details
            fmt = ("Command: %(cmd)s\n"
                   "Timeout: %(to)s\n"
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

        # Keep pylint quiet
        del stdin
        # This is an abstract method
        raise DockerNotImplementedError

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
            return None
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

        if self.docker_command is not None:
            complete = self.docker_command.strip()
        else:
            complete = ""
        if self.docker_options is not None:
            complete = "%s %s" % (complete.strip(),
                                  self.docker_options.strip())
        if self.subcmd is not None:
            complete = "%s %s" % (complete.strip(), self.subcmd.strip())
        if len(self.subargs) > 0:
            complete = "%s %s" % (complete.strip(), " ".join(self.subargs))
        return complete.strip()


# Normally we need two public methods minimum, however extensions
# will be made to this class in the future.
class DockerCmd(DockerCmdBase):  # pylint: disable=R0903

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
        else:
            str_stdin = ""
        if self.verbose:
            self.subtest.logdebug("Executing %s%s", str(self), str_stdin)
        self.cmdresult = utils.run(self.command, timeout=self.timeout,
                                   stdin=stdin, verbose=False,
                                   ignore_status=True)
        # Return value, not reference
        return self.cmdresult


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
        else:
            str_stdin = ""
        if self.verbose:
            self.subtest.logdebug("Async-execute: %s%s", str(self), str_stdin)
        self._async_job = utils.AsyncJob(self.command, verbose=False,
                                         stdin=stdin, close_fds=True)
        return self.cmdresult

    def wait_for_ready(self, cid=None, timeout=None, timestep=0.2):
        """
        Monitor the output of a container (including docker logs, in
        case stdout is detached), waiting for the string 'READY' or
        for the container to terminate. Return if we see the string.
        If we don't, throw a meaningful exception.

        :raises DockerExecError: on timeout.
        """
        if timeout is None:
            timeout = self.timeout
        end_time = time.time() + timeout
        done = False
        while time.time() <= end_time and not done:
            done = self.done
            stdout = self.stdout
            if 'READY' in stdout:
                return
            # Also check docker logs
            if cid is None:
                cid = self.container_id
            if cid is not None:
                logs = DockerCmd(self.subtest, 'logs', [cid])
                logs.execute()
                stdout = logs.stdout
                if 'READY' in stdout:
                    return
            time.sleep(timestep)

        # Never saw READY. Did container exit? If so, help user understand why
        if self.done:
            msg = "Container exited before READY"
            if self.exit_status == 0:
                msg += " (normal exit status)"
            else:
                msg += "; exit status = %d" % self.exit_status
            stderr = self.stderr
            if stderr:
                msg += "; stderr='%s'" % stderr
            raise DockerExecError(msg)

        # Container still running. Must be a timeout.
        msg = "Timed out waiting for container READY"
        if stdout:
            msg += "; stdout='%s'" % stdout
        raise DockerExecError(msg)

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

    @property
    def done(self):
        """
        Return True if processes has ended (successful or not)

        :raises DockerTestError: execute() was not called first
        :raises DockerCommandError: If timeout exceeded
        """

        if self._async_job is None:
            raise DockerTestError("Attempted to wait for done before execute()"
                                  " called.")
        if self.duration >= self.timeout:
            # Exception takes care of logging the command
            raise DockerCommandError("Timed out after %0.2f seconds"
                                     % (float(self.timeout)),
                                     self.cmdresult)
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

    @property
    def container_id(self):
        """
        Try to discover our own container ID or name. Return None if we can't.
        """

        # The simple case: if we are a docker attach command, assume that
        # subargs are zero or more flags plus a container ID or name.
        if self.subcmd == 'attach':
            return self.subargs[-1]

        # Non-attach command. Find our PID, iterate over all containers,
        # get their PID (via inspect). If we find a match, return the CID.
        pid = self.process_id
        cids = utils.run('docker ps -q', verbose=False).stdout.splitlines()
        for cid in cids:
            c_pid = utils.run('docker inspect --format {{.State.Pid}} ' + cid)
            if int(c_pid.stdout) == int(pid):
                return cid
        return None

    # Override base-class property methods to give up-to-second details

    @property
    def cmdresult(self):
        # FIXME: Can't seem to assign to parent-class property
        #        using private attribute instead, uggg.
        if self._async_job is None:
            return None
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
        """
        Returns difference between start time and now.

        returns: time in seconds
        rtype: float
        """
        if self._async_job is None:
            return None
        if self._async_job.sp.poll() is not None:
            # Total elapsed time
            duration = self._async_job.result.duration
        else:
            # Current elapsed time
            duration = time.time() - self._async_job.start_time
        return float(duration)
