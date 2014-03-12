"""
Test executing /bin/true inside a container returns exit code 0
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest import subtest, images
from dockertest.dockercmd import DockerCmd
from dockertest.output import OutputGood

class run_true(subtest.Subtest):
    version = "0.2.3"  #  Used to track when setup() should run
    config_section = 'docker_cli/run_true'

    def initialize(self):
        fin = images.DockerImage.full_name_from_defaults(self.config)
        self.config['subargs'] = self.config['run_options_csv'].split(',')
        self.config['subargs'].append(fin)
        self.config['subargs'].append('/bin/true')

    def run_once(self):
        super(run_true, self).run_once() # Prints out basic info
        dkrcmd = DockerCmd(self, 'run', self.config['subargs'])
        self.config['cmdresult'] = dkrcmd.execute()

    def postprocess(self):
        super(run_true, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        OutputGood(self.config['cmdresult'])
        expected = self.config['exit_status']
        self.failif(self.config['cmdresult'].exit_status != expected,
                    "Exit status of /bin/true non-zero!")
        self.logdebug(self.config['cmdresult'])
