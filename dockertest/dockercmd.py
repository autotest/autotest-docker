"""
Frequently used docker CLI operations/data
"""

from autotest.client import utils
from subtest import Subtest

class DockerCmd(utils.CmdResult):
    """
    Strings positional arguments together, execute, represent results.
    """

    #: Do not raise an exception if command returns non-zero exit code
    ignore_status = True

    #: No command should last more than an hour by default
    timeout = 60 * 60

    #: Rely on higher layers to handle or ignore info.
    verbose = True

    #: Subclasses can override this if feeding stdin required
    #: from string, file-descriptor, or file-like.
    stdin_file = None

    #

    def __init__(self, subtest, subcommand, *subargs):
        """
        Initialize extended results from docker subcommand, ignoring exceptions.

        :param subtest: A subtest.Subtest subclass instance
        :param subcommand: A Subcommand or single option string
        :param *subargs: (optional) additional args to Subcommand
        """
        if not isinstance(subtest, Subtest):
            raise ValueError("subtest is not a Subtest subclass or derivative")
        else:
            self.subtest = subtest
        # Throw exception if not string-convertible
        self.subcommand = str(subcommand)
        # Throw exception if not list-convertible
        self.subargs = list(subargs)
        cmdresult = self.execute()
        super(DockerCmd, self).__init__(command=cmdresult.command,
                                        stdout=cmdresult.stdout,
                                        stderr=cmdresult.stderr,
                                        exit_status=cmdresult.exit_status,
                                        duration=cmdresult.duration)

    @property
    def docker_options(self):
        """
        String of docker args
        """
        return self.subtest.config.get('docker_options', '')

    @property
    def docker_command(self):
        """
        String of docker command + docker args
        """
        return self.subtest.config.get('docker_path', 'docker')

    @property
    def args(self):
        """
        Tuple of options + subcommand + args
        """
        docker_optlist = self.docker_options.split()
        return tuple(docker_optlist + [self.subcommand] + self.subargs)

    @property
    def full_command(self):
        """
        String representation of command + subcommand + args
        """
        return "%s %s" % (self.docker_command, " ".join(self.args))

    def execute(self):
        """
        Return a CmdResult instance from executing fully-formed command
        """
        if self.verbose:
            self.subtest.logdebug("Running '%s'", self.full_command)
        return utils.run(command = self.docker_command,
                         timeout = self.timeout,
                         ignore_status = self.ignore_status,
                         verbose = self.verbose,
                         stdin = self.stdin_file,
                         args = self.args)


class NoFailDockerCmd(DockerCmd):
    """
    Raise error.CmdError if command results in non-zero exit code
    """
    ignore_status = False
