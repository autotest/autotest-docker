"""
Test executing /bin/false inside a container returns exit code 0
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest import subtest, images
from dockertest.dockercmd import DockerCmd
from dockertest.output import OutputGood

class run_false(subtest.Subtest):
    config_section = 'docker_cli/run_false'

    def initialize(self):
        fin = images.DockerImage.full_name_from_defaults(self.config)
        self.stuff['subargs'] = self.config['run_options_csv'].split(',')
        self.stuff['subargs'].append(fin)
        self.stuff['subargs'].append('/bin/false')

    def run_once(self):
        super(run_false, self).run_once() # Prints out basic info
        dkrcmd = DockerCmd(self, 'run', self.stuff['subargs'])
        self.stuff['cmdresult'] = dkrcmd.execute()

    def postprocess(self):
        super(run_false, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        OutputGood(self.stuff['cmdresult'])
        expected = self.config['exit_status']
        self.failif(self.stuff['cmdresult'].exit_status != expected,
                    "Exit status of /bin/false zero: %s"
                    % self.stuff['cmdresult'])
        self.logdebug(self.stuff['cmdresult'])
