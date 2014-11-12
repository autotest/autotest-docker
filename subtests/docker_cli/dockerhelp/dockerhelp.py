r"""
Summary
---------

Test various odd-ball options/arguments produce usage info / helpful output

Operational Summary
--------------------

#. Run docker command with various combinations of options/args
#. Check results are expected
"""

from dockertest.config import Config
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.output import OutputGood
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller


# 'help()' is reserved in python
class dockerhelp(SubSubtestCaller):
    config_section = 'docker_cli/dockerhelp'

    def initialize(self):
        gsl = 'generate_subsubtest_list'
        if gsl not in self.config or not self.config[gsl]:
            super(dockerhelp, self).initialize()
        else:
            self.loginfo(self.__class__.__name__ + ": initialize()")
            commands = self.config['help_commands'].split()
            subsubtests = ['help_' + x for x in commands]
            if 'subsubtests' in self.config:
                sst = self.config['subsubtests'].strip().split(',')
                subsubtests = sst + subsubtests
            self.subsubtest_names = subsubtests


class help_base(SubSubtest):

    def initialize(self):
        super(help_base, self).initialize()  # Prints out basic info
        # Names are too long to put on one line
        sol = 'success_option_list'
        fol = 'failure_option_list'
        self.sub_stuff[sol] = []
        self.sub_stuff[fol] = []
        if sol in self.config:
            self.sub_stuff[sol] = self.config[sol].split(',')
        if fol in self.config:
            self.sub_stuff[fol] = self.config[fol].split(',')
        self.sub_stuff["success_cmdresults"] = []
        self.sub_stuff['failure_cmdresults'] = []

    def run_once(self):
        super(help_base, self).run_once()  # Prints out basic info
        for option in self.sub_stuff['success_option_list']:
            # No successful command should throw an exception
            dkrcmd_results = mustpass(DockerCmd(self,
                                                option).execute())
            self.sub_stuff["success_cmdresults"].append(dkrcmd_results)
        for option in self.sub_stuff['failure_option_list']:
            # These are likely to return non-zero
            dkrcmd = DockerCmd(self, option)
            self.sub_stuff['failure_cmdresults'].append(dkrcmd.execute())

    def postprocess(self):
        super(help_base, self).postprocess()  # Prints out basic info
        for cmdresult in self.sub_stuff["success_cmdresults"]:
            self.failif(cmdresult.exit_status != 0,
                        "Docker command returned non-zero exit status")
            no_usage = cmdresult.stdout.lower().find('usage:') == -1
            self.failif(no_usage, "Did not return usage help on stdout for: "
                        "%s" % cmdresult.command)
            outputgood = OutputGood(cmdresult, ignore_error=True,
                                    skip=['usage_check', 'error_check'])
            self.failif(not outputgood, str(outputgood))
        for cmdresult in self.sub_stuff['failure_cmdresults']:
            self.failif(cmdresult.exit_status == 0,
                        "Invalid docker option returned exit status of '0'")
            # https://bugzilla.redhat.com/show_bug.cgi?id=1098280
            defined = cmdresult.stdout.lower().find('flag provided but '
                                                    'not defined') > -1
            usage = cmdresult.stdout.lower().find('usage:') > -1
            self.failif(defined or usage, 'Did not return undefined '
                        'error or usage message for: '
                        "%s" % cmdresult.command)
            outputgood = OutputGood(cmdresult, ignore_error=True,
                                    skip=['usage_check'])
            self.failif(not outputgood, str(outputgood))


class help_simple(help_base):
    # differs from help_base by dockerhelp.ini
    pass


def help_class_factory(name):
    """Subsubclass generator for all help subargs"""

    class help_class(help_base):

        def initialize(self):
            super(help_class, self).initialize()
            # if not overridden by the config, set self help as default
            sol = 'success_option_list'
            if not bool(self.sub_stuff[sol]):
                self.sub_stuff[sol] = ["help " + name,
                                       name + " --help"]

    key = "help_" + name
    help_class.__name__ = key
    return key, help_class


config = Config()['docker_cli/dockerhelp']
if 'help_commands' in config:
    help_commands = config['help_commands'].strip().split()
    globes = globals()
    for i in help_commands:
        _key, _val = help_class_factory(i)
        globes[_key] = _val
