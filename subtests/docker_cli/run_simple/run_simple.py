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
        self.subStuff['subargs'] = self.config['run_options_csv'].split(',')
        fin = DockerImage.full_name_from_defaults(self.config)
        self.subStuff['subargs'].append(fin)
        self.subStuff['subargs'].append('/bin/bash')
        self.subStuff['subargs'].append('-c')
        self.subStuff['subargs'].append(self.config['cmd'])

    def run_once(self):
        super(run_base, self).run_once()    # Prints out basic info
        dkrcmd = DockerCmd(self.parentSubtest, 'run', self.subStuff['subargs'])
        self.subStuff['cmdresult'] = dkrcmd.execute()

    def postprocess(self):
        super(run_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        OutputGood(self.subStuff['cmdresult'])
        expected = self.config['exit_status']
        self.failif(self.subStuff['cmdresult'].exit_status != expected,
                    "Exit status of /bin/true non-zero: %s"
                    % self.subStuff['cmdresult'])
        self.logdebug(self.subStuff['cmdresult'])
