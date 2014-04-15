"""
Test could not run a container which is already running

1. Run a container with a certain name
2. Run a container with a certain name again
3. Fail to run a container again
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from autotest.client import utils
from dockertest import subtest
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.output import OutputGood


class run_twice(subtest.Subtest):
    config_section = 'docker_cli/run_twice'

    def initialize(self):
        super(run_twice, self).initialize()
        name = self.stuff['container_name'] = utils.generate_random_string(12)
        subargs = ['--name=%s' % name]
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append('/bin/bash')
        subargs.append('-c')
        cmd = '\'echo test\''
        subargs.append(cmd)
        self.stuff['subargs'] = subargs
        self.stuff['cmdresults'] = []
        self.stuff['2nd_cmdresults'] = []

    def run_once(self):
        super(run_twice, self).run_once()
        nfdc = NoFailDockerCmd(self, 'run', self.stuff['subargs'])
        self.stuff['cmdresults'].append(nfdc.execute())
        dc = DockerCmd(self, 'run', self.stuff['subargs'])
        self.stuff['2nd_cmdresults'].append(dc.execute())

    def postprocess(self):
        super(run_twice, self).postprocess()
        for cmdresult in self.stuff['cmdresults']:
            self.loginfo("command: '%s'" % cmdresult.command)
            outputgood = OutputGood(cmdresult)
            self.failif(not outputgood, str(outputgood))
        for cmdresult in self.stuff['2nd_cmdresults']:
            self.loginfo("command: '%s'" % cmdresult.command)
            outputgood = OutputGood(cmdresult, ignore_error=True,
                                    skip=['error_check'])
            self.failif(cmdresult.exit_status == 0, str(outputgood))
            if cmdresult.exit_status != 0:
                self.logerror("Intend to fail:\n%s" % cmdresult.stderr.strip())

    def cleanup(self):
        super(run_twice, self).cleanup()
        if self.config['remove_after_test']:
            dkrcmd = DockerCmd(self, 'rm', [self.stuff['container_name']])
            dkrcmd.execute()
