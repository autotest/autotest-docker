"""
Frequently used docker CLI operations/data
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

from autotest.client.shared import error
from autotest.client import utils
from subtest import Subtest
from xceptions import DockerExecError, DockerCommandError
from xceptions import  DockerNotImplementedError

class DockerCmdBase(object):
    """
    Setup a call docker subcommand as if by CLI w/ subtest config integration
    """

    def __init__(self, subtest, subcmd, subargs=None, timeout=None):
        """
        Execute docker subcommand with arguments and a timeout.

        :param subtest: A subtest.Subtest subclass instance
        :param subcomd: A Subcommand or single option string
        :param subargs: (optional) Iterable of additional args to subcommand
        :param timeout: Seconds to wait before terminating docker command
                        None to use 'docker_timeout' config. option.
        :raise: DockerCommandError on incorrect usage
        """
        # Prevent accidental test.test instance passing
        if not isinstance(subtest, Subtest):
            raise DockerCommandError("Subtest is not a Subtest instance or "
                                     "subclass.")
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

    def __str__(self):
        """
        Return full command-line string (wrapps command property)
        """
        return self.command

    def execute(self, stdin):
        """
        Execute docker subcommand

        :param stdin: String or file-like containing standard input contents
        :raise: DockerCommandError on incorrect usage
        :raise: DockerExecError on command failure
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
    """

    def execute(self, stdin=None):
        """
        Run docker command, ignore any non-zero exit code

        :param stdin: String or file-like containing standard input contents
        :raise: DockerCommandError on incorrect usage
        :raise: DockerExecError on command failure
        :return: A CmdResult instance
        """
        try:
            return utils.run(self.command, timeout=self.timeout,
                             stdin=stdin, verbose=False, ignore_status=True)
        # ignore_status=True : should not see CmdError
        except error.CmdError, detail:
            # Something internal must have gone wrong
            raise DockerCommandError(str(detail.result_obj))

class NoFailDockerCmd(DockerCmd):
    """
    Setup a call docker subcommand as if by CLI w/ subtest config integration
    """

    def execute(self, stdin=None):
        """
        Execute docker command, raising DockerCommandError if non-zero exit

        :param stdin: String or file-like containing standard input contents
        :raise: DockerCommandError on incorrect usage
        :raise: DockerExecError on if command retuns non-zero exit code
        :return: A CmdResult instance
        """
        try:
            return utils.run(self.command, timeout=self.timeout,
                             stdin=stdin, verbose=False, ignore_status=False)
        # Prevent caller from needing to import this exception class
        except error.CmdError, detail:
            raise DockerExecError(str(detail.result_obj))

class MustFailDockerCmd(DockerCmd):
    """
    Setup a call docker subcommand as if by CLI w/ subtest config integration
    """

    def execute(self, stdin=None):
        """
        Execute docker command, raise DockerExecError if **zero** exit code

        :param stdin: String or file-like containing standard input contents
        :raise: DockerCommandError on incorrect usage
        :raise: DockerExecError on if command retuns zero exit code
        :return: A CmdResult instance
        """
        try:
            cmdresult = utils.run(self.command, timeout=self.timeout,
                                  stdin=stdin, verbose=False,
                                  ignore_status=True)
        # Prevent caller from needing to import this exception class
        except error.CmdError, detail:
            raise DockerCommandError(str(detail.result_obj))
        if cmdresult.exit_status == 0:
            raise DockerExecError("Unexpected command success: %s"
                                  % str(cmdresult))
        else:
            return cmdresult

class AsyncDockerCmd(DockerCmdBase):
    """
    Execute docker command, self.cmdresult.exit_status != None when done
    """

    #: Used internally by execute()
    _async_job = None

    def execute(self, stdin=None):
        """
        Start execution of asynchronous docker command

        :param stdin: String or file-like containing standard input contents
        :raise: DockerCommandError on incorrect usage
        :return: A partial CmdResult instance
        """
        self._async_job = utils.AsyncJob(self.command, verbose=False,
                                         stdin=stdin)
        return self._async_job.result

    def wait(self):
        """
        Return CmdResult after waiting for process to end or timeout

        :raise: DockerCommandError on incorrect usage
        """
        if self._async_job is not None:
            return self._async_job.wait_for(self.timeout)
        else:
            raise DockerCommandError("Attempted to wait before "
                                     "execute() called")

    @property
    def done(self):
        """
        Return True if processes has ended
        """
        if self._async_job is None:
            raise DockerCommandError("Cannot finsh before starting")
        return self._async_job.sp.poll() is not None

    @property
    def stdout(self):
        """
        Represent string of stdout so far

        :raise: DockerCommandError on incorrect usage
        """
        if self._async_job is not None:
            return self._async_job.get_stdout
        else:
            raise DockerCommandError("Attempted to access stdout before "
                                     "execute() called")

    @property
    def stderr(self):
        """
        Represent string of stderr output so far

        :raise: DockerCommandError on incorrect usage
        """
        if self._async_job is not None:
            return self._async_job.get_stderr
        else:
            raise DockerCommandError("Attempted to access stderr before "
                                     "execute() called")

    @property
    def process_id(self):
        """
        Return the process id of the backgtround job
        """
        if self._async_job is not None:
            return self._async_job.sp.pid
        else:
            raise DockerCommandError("Attempted to access pid before "
                                     "execute() called")
