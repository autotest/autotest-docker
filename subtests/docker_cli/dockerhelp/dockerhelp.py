"""
Test various odd-ball options/arguments produce usage info / helpful output

1. Suck in two csv lists of options to pass
2. Run docker commnd with those options one-by-one
3. Check results.
"""

from autotest.client import utils
from dockertest import subtest, output

# 'help()' is reserved in python
class dockerhelp(subtest.Subtest):
    version = "0.0.1"  #  Used to track when setup() should run
    config_section = 'docker_cli/dockerhelp'

    def initialize(self):
        super(dockerhelp, self).initialize() # Prints out basic info
        self.config['docker_command'] = ("%s %s" % (self.config['docker_path'],
                               self.config['docker_options']))
        sol = 'success_option_list'
        self.config[sol] = self.config[sol].split(',')
        fol = 'failure_option_list'
        self.config[fol] = self.config[fol].split(',')
        self.config["success_cmdresults"] = []
        self.config['failure_cmdresults'] = []

    def run_once(self):
        super(dockerhelp, self).run_once() # Prints out basic info
        for option in self.config['success_option_list']:
            command = '%s %s' % (self.config['docker_command'], option)
            # No successful command should throw an exception
            self.config["success_cmdresults"].append(utils.run(command,
                                                     ignore_status=False))
        for option in self.config['failure_option_list']:
            command = '%s %s' % (self.config['docker_command'], option)
            # These are likely to return non-zero
            self.config['failure_cmdresults'].append(utils.run(command,
                                                     ignore_status=True))

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
            output.crash_check(cmdresult.stderr)
            output.crash_check(cmdresult.stdout)
        for cmdresult in self.config['failure_cmdresults']:
            self.loginfo("command: '%s'" % cmdresult.command)
            self.failif(cmdresult.exit_status == 0,
                        "Invalid docker option returned exit status of '0'")
            output.crash_check(cmdresult.stderr)
            output.crash_check(cmdresult.stdout)
