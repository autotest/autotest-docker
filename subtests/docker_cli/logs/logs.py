r"""
Summary
----------

Monitor various container states and stdio in parallel with the ``logs``
command.

Operational Summary
----------------------

#. Create a container, run a docker logs command
#. Capture new logs output
#. Start the container, capture new logs output
#. Stop container, capture new logs output
#. Verify produced output with expected output

Prerequisites
---------------------------------------------
*  Host clock is accurate, local timezone setup properly.
*  Host clock does not change drastically during test
*  Starting and executing the test container takes under one minute
"""

from dockertest.subtest import SubSubtestCaller
from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.config import get_as_list


class logs(SubSubtestCaller):
    pass


class Base(SubSubtest):

    def initialize(self):
        super(Base, self).initialize()
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['cntnr_names'] = []

    def cleanup(self):
        super(Base, self).cleanup()
        if self.config['remove_after_test']:
            for cntnr_name in self.sub_stuff['cntnr_names']:
                DockerCmd(self, 'rm', ['--force', cntnr_name],
                          verbose=False).execute()

    @staticmethod
    def scrape_name(subargs):
        """
        Return the next argument after the ``--name`` item in subargs or None
        """
        try:
            return subargs[subargs.index('--name') + 1]
        except IndexError:
            return None

    def create_cntnr(self, command, args='', execute=True, cls=DockerCmd):
        """
        Return possibly executed DockerCmd instance

        :param name: Name for container
        :param command: Command argument for container
        :param args: Complete, space-separated argument list for container
        :param execute:  If true, execute() will be called on instance
        :param cls: A DockerCmdBase subclass to use for instance
        :return: A new DockerCmd instance
        """
        fqin = DockerImage.full_name_from_defaults(self.config)
        name = self.sub_stuff['dc'].get_unique_name()
        # scrape_names (above) depends on separate name argument from --name
        subargs = ['--name', name]
        subargs += get_as_list(self.config['extra_create_args'])
        subargs += [fqin, command]
        subargs += args.strip().split()
        dockercmd = cls(self, 'create', subargs, verbose=True)
        dockercmd.quiet = True
        if execute:
            dockercmd.execute()
            mustpass(dockercmd.cmdresult)
        self.sub_stuff['cntnr_names'].append(name)
        return dockercmd

    def start_cntnr(self, name, execute=True, cls=DockerCmd):
        """
        Return possibly executed DockerCmd instance

        :param name: Name for container
        :param execute:  If true, execute() will be called on instance
        :param cls: A DockerCmdBase subclass to use for instance
        :return: A new DockerCmd instance
        """
        subargs = get_as_list(self.config['extra_start_args']) + [name]
        dockercmd = cls(self, 'start', subargs, verbose=False)
        dockercmd.quiet = True
        if execute:
            dockercmd.execute()
            mustpass(dockercmd.cmdresult)
        return dockercmd

    def logs_cmd(self, name, args='', execute=True, cls=DockerCmd):
        """
        Return possibly executed DockerCmd instance

        :param args: Complete, space-separated argument list for container
        :param name: Name for container
        :param execute:  If true, execute() will be called on instance
        :param cls: A DockerCmdBase subclass to use for instance
        :return: A new DockerCmd instance
        """
        subargs = args.strip().split()
        subargs += [name]
        # This is test subject, provide additional details
        dockercmd = cls(self, 'logs', subargs, verbose=True)
        dockercmd.quiet = False
        if execute:
            dockercmd.execute()
        return dockercmd
