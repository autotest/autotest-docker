"""
Sub-subtest module used by dockerimport test

1. Create a tarball with some dummy content
2. Chop the tarball at some pre-defined point
3. Attempt to feed incomplete tarball into docker import
4. Verify import failed
"""

import os.path
from autotest.client import utils
from empty import empty
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustfail
from dockertest import output


class truncated(empty):

    TARFILENAME = 'bad.tar'

    def cleanup(self):
        # Call empty parent's cleanup, not empty's.
        super(empty, self).cleanup()  # pylint: disable=E1003
        # Fail test if **successful**
        image_name = self.sub_stuff['image_name']  # assume id lookup failed
        if self.parent_subtest.config['remove_after_test']:
            dkrcmd = DockerCmd(self, 'rmi', [image_name])
            mustfail(dkrcmd.execute())

    def run_tar(self, tar_command, dkr_command):
        tarfile = os.path.join(self.parent_subtest.bindir, self.TARFILENAME)
        command = "cat %s | %s" % (tarfile, dkr_command)
        self.loginfo("Expected to fail: %s", command)
        self.sub_stuff['cmdresult'] = utils.run(command, ignore_status=True,
                                                verbose=True)

    def check_output(self):
        outputgood = output.OutputGood(self.sub_stuff['cmdresult'],
                                       ignore_error=True)
        zeroexit = self.sub_stuff['cmdresult'].exit_status == 0
        # This is SUPPOSE to fail, fail test if it succeeds!
        self.failif(outputgood or zeroexit,
                    "Unexpected good output: %s or exit_status: %d"
                    % (outputgood, self.sub_stuff['cmdresult'].exit_status))

    def check_status(self):
        successful_exit = self.sub_stuff['cmdresult'].exit_status == 0
        self.failif(successful_exit, "Unexpected command success!")
        self.loginfo("It failed as expected")

    def image_check(self):
        image_id = self.sub_stuff.get('image_id')
        self.failif(image_id is not None,
                    "Image ID '%s' successfully retrieved after expected "
                    "import failure!" % image_id)
