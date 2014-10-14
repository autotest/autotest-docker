r"""
Summary
---------

Set of tests that modifies files within an image and then
asserts the changes are picked up correctly by ``docker diff``

Operational Summary
--------------------

#. Modify a file in a docker image
#. Run docker diff on resultant container
#. Check output against expected changes

Prerequisites
---------------

*  Docker daemon is running and accessible by it's unix socket.
   ``docker_cli/diff`` Configuration
"""

from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.images import DockerImage
from dockertest.containers import DockerContainers
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller


class diff(SubSubtestCaller):
    pass


class diff_base(SubSubtest):

    @staticmethod
    def parse_diff_output(output):
        xsplit = [x.split() for x in output.split('\n') if x]
        ysplit = [(y[1], y[0]) for y in xsplit]
        return dict(ysplit)

    def initialize(self):
        super(diff_base, self).initialize()
        dc = DockerContainers(self.parent_subtest)
        name = self.sub_stuff['name'] = dc.get_unique_name()
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs = ['--name=%s' % (name), fin]
        subargs = subargs + self.config['command'].split(',')
        nfdc = NoFailDockerCmd(self, 'run', subargs)
        nfdc.execute()

    def run_once(self):
        super(diff_base, self).run_once()
        nfdc = NoFailDockerCmd(self, 'diff', [self.sub_stuff['name']])
        self.sub_stuff['cmdresult'] = nfdc.execute()

    def postprocess(self):
        super(diff_base, self).postprocess()
        diffmap = self.parse_diff_output(self.sub_stuff['cmdresult'].stdout)
        files_changed = self.config['files_changed'].split(',')
        odds = files_changed[1::2]
        even = files_changed[::2]
        expected = zip(odds, even)
        for key, value in expected:
            self.failif(key not in diffmap,
                        "Change to file: %s not detected." % (key))
            self.failif(value != diffmap[key],
                        "Change type detection error for "
                        "change: %s %s" % (value, key))

    def cleanup(self):
        super(diff_base, self).cleanup()
        if self.config['remove_after_test']:
            dkrcmd = DockerCmd(self, 'rm', [self.sub_stuff['name']])
            dkrcmd.execute()


class diff_add(diff_base):
    pass  # only change in configuration


class diff_change(diff_base):
    pass  # only change in configuration


class diff_delete(diff_base):
    pass  # only change in configuration
