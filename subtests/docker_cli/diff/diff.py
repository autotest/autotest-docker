"""
Test output of docker diff command

1. Modify a file in a docker image
2. Run docker diff on resultant container
3. Check output against expected changes
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from autotest.client import utils
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.images import DocdokerImage
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
import os

class diff(SubSubtestCaller):
    config_section = 'docker_cli/diff'

class diff_base(SubSubtest):
    @staticmethod
    def parse_diff_output(output):
        return dict([(y[1], y[0]) for y in
                    [x.split() for x in output.split('\n') if x]])

    def initialize(self):
        super(diff_base, self).initialize()
        name = self.sub_stuff['name'] = utils.generate_random_string(12)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs = ['--name=%s' % (name), fin]
        subargs = subargs + self.config['command'].split(',')
        nfdc = NoFailDockerCmd(self.parent_subtest,
                               'run',
                               subargs)
        nfdc.execute()

    def run_once(self):
        super(diff_base, self).run_once()
        nfdc = NoFailDockerCmd(self.parent_subtest,
                               'diff',
                               [self.sub_stuff['name']])
        self.sub_stuff['cmdresult'] = nfdc.execute()

    def postprocess(self):
        super(diff_base, self).postprocess()
        diffmap = self.parse_diff_output(self.sub_stuff['cmdresult'].stdout)
        expected = self.config['files_changed'].split(',')
        expected = dict(zip(expected[1::2], expected[::2]))
        for i in expected.keys():
            self.failif(not diffmap.has_key(i),
                        "Change to file: %s not detected." % (i))
            self.failif(expected[i] != diffmap[i],
                        "Change type detection error for "
                        "change: %s %s" % (expected[i], i))

    def cleanup(self):
        super(diff_base, self).cleanup()
        if self.config['remove_after_test']:
            dkrcmd = DockerCmd(self.parent_subtest,
                               'rm',
                               [self.sub_stuff['name']])
            cmd = dkrcmd.execute()

class diff_add(diff_base):
    pass #only change in configuration

class diff_change(diff_base):
    pass #only change in configuration

class diff_delete(diff_base):
    pass #only change in configuration
