"""
Test various odd-ball options/arguments produce usage info / helpful output

1. Suck in two csv lists of options to pass
2. Run docker commnd with those options one-by-one
3. Check results
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest import subtest
from dockertest.output import OutputGood
from dockertest.dockercmd import DockerCmd, NoFailDockerCmd

# 'help()' is reserved in python
class dockerhelp(subtest.Subtest):
    version = "0.0.1"  #  Used to track when setup() should run
    config_section = 'docker_cli/dockerhelp'

    def initialize(self):
        super(dockerhelp, self).initialize() # Prints out basic info
        # Names are too long to put on one line
        sol = 'success_option_list'
        fol = 'failure_option_list'
        self.config[sol] = self.config[sol].split(',')
        self.config[fol] = self.config[fol].split(',')
        self.config["success_cmdresults"] = []
        self.config['failure_cmdresults'] = []

    def run_once(self):
        super(dockerhelp, self).run_once() # Prints out basic info
        for option in self.config['success_option_list']:
            # No successful command should throw an exception
            dkrcmd = NoFailDockerCmd(self, option)
            self.config["success_cmdresults"].append(dkrcmd.execute())
        for option in self.config['failure_option_list']:
            # These are likely to return non-zero
            dkrcmd = DockerCmd(self, option)
            self.config['failure_cmdresults'].append(dkrcmd.execute())

    def postprocess(self):
        super(dockerhelp, self).postprocess()  # Prints out basic info
        for cmdresult in self.config["success_cmdresults"]:
            self.loginfo("command: '%s'" % cmdresult.command)
            self.failif(cmdresult.exit_status != 0,
                        "Docker command returned non-zero exit status")
            self.failif(cmdresult.stderr.count('Usage:') < 1,
                        "Docker command did not return usage info on stderr")
            self.failif(cmdresult.stderr.count('Commands:') < 1,
                        "Docker command did not return command-line help "
                        "on stderr.")
            outputgood = OutputGood(cmdresult, ignore_error=True,
                                    skip=['usage_check'])
            self.failif(not outputgood, str(outputgood))
        for cmdresult in self.config['failure_cmdresults']:
            self.loginfo("command: '%s'" % cmdresult.command)
            self.failif(cmdresult.exit_status == 0,
                        "Invalid docker option returned exit status of '0'")
            outputgood = OutputGood(cmdresult, ignore_error=True,
                                    skip=['usage_check'])
            self.failif(not outputgood, str(outputgood))
