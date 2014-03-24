"""
Test docker run by executing basic commands inside container and checking the
results.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest.subtest import SubSubtest, SubSubtestCaller
from dockertest.dockercmd import DockerCmd
from dockertest.output import OutputGood
from dockertest.images import DockerImage


class run_simple(SubSubtestCaller):
    config_section = 'docker_cli/run_simple'


class run_base(SubSubtest):

    def initialize(self):
        super(run_base, self).initialize()
        self.sub_stuff['subargs'] = self.config['run_options_csv'].split(',')
        fin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['subargs'].append(fin)
        self.sub_stuff['subargs'].append('/bin/bash')
        self.sub_stuff['subargs'].append('-c')
        self.sub_stuff['subargs'].append(self.config['cmd'])

    def run_once(self):
        super(run_base, self).run_once()    # Prints out basic info
        dkrcmd = DockerCmd(self.parent_subtest, 'run', self.sub_stuff['subargs'])
        self.sub_stuff['cmdresult'] = dkrcmd.execute()

    def postprocess(self):
        super(run_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        OutputGood(self.sub_stuff['cmdresult'])
        expected = self.config['exit_status']
        self.failif(self.sub_stuff['cmdresult'].exit_status != expected,
                    "Exit status of /bin/true non-zero: %s"
                    % self.sub_stuff['cmdresult'])
        self.logdebug(self.sub_stuff['cmdresult'])

class run_true(run_base):
    pass  # Only change is in configuration

class run_false(run_base):
    pass  # Only change is in configuration



