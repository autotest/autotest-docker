r"""
Summary
---------

Test various odd-ball options/arguments produce usage info / helpful output

Operational Summary
--------------------

#. Suck in two csv lists of options to pass
#. Run docker commnd with those options one-by-one
#. Check results

Prerequesites
----------------

*  Running docker daemon

Configuration
-------------------------------------------

*  The ``success_option_list`` is a CSV list of docker options
   where a zero-exit code is expected (though a usage message
   may appear)
*  The ``failure_option_list`` is the opposite.
"""

from dockertest import subtest
from dockertest.output import OutputGood
from dockertest.dockercmd import DockerCmd, NoFailDockerCmd

# 'help()' is reserved in python


class dockerhelp(subtest.Subtest):
    config_section = 'docker_cli/dockerhelp'

    def initialize(self):
        super(dockerhelp, self).initialize()  # Prints out basic info
        # Names are too long to put on one line
        sol = 'success_option_list'
        fol = 'failure_option_list'
        self.stuff["success_cmdresults"] = []
        self.stuff['failure_cmdresults'] = []
        self.stuff[sol] = []
        self.stuff[fol] = []
        if sol in self.config:
            self.stuff[sol] = self.config[sol].split(',')
        if fol in self.config:
            self.stuff[fol] = self.config[fol].split(',')

    def run_once(self):
        super(dockerhelp, self).run_once()  # Prints out basic info
        for option in self.stuff['success_option_list']:
            # No successful command should throw an exception
            dkrcmd = NoFailDockerCmd(self, option)
            self.stuff["success_cmdresults"].append(dkrcmd.execute())
        for option in self.stuff['failure_option_list']:
            # These are likely to return non-zero
            dkrcmd = DockerCmd(self, option)
            self.stuff['failure_cmdresults'].append(dkrcmd.execute())

    def postprocess(self):
        super(dockerhelp, self).postprocess()  # Prints out basic info
        for cmdresult in self.stuff["success_cmdresults"]:
            self.loginfo("command: '%s'" % cmdresult.command)
            self.failif(cmdresult.exit_status != 0,
                        "Docker command returned non-zero exit status")
            self.failif(cmdresult.stderr.count('Usage:') < 1 and
                        cmdresult.stdout.count('Usage:') < 1,
                        "Docker command did not return usage info on stderr")
            self.failif(cmdresult.stderr.count('Commands:') < 1 and
                        cmdresult.stdout.count('Usage:') < 1,
                        "Docker command did not return command-line help "
                        "on stderr.")
            outputgood = OutputGood(cmdresult, ignore_error=True,
                                    skip=['usage_check', 'error_check'])
            self.failif(not outputgood, str(outputgood))
        for cmdresult in self.stuff['failure_cmdresults']:
            self.loginfo("command: '%s'" % cmdresult.command)
            self.failif(cmdresult.exit_status == 0,
                        "Invalid docker option returned exit status of '0'")
            outputgood = OutputGood(cmdresult, ignore_error=True,
                                    skip=['usage_check'])
            self.failif(not outputgood, str(outputgood))
