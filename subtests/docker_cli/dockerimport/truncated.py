"""
Sub-subtest module used by dockerimport test

1. Create a tarball with some dummy content
2. Chop the tarball at some pre-defined point
3. Attempt to feed incomplete tarball into docker import
4. Verify import failed
"""

from autotest.client import utils
import tempfile
import os
import os.path
import shutil
from empty import empty
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustfail
from dockertest import output


class truncated(empty):

    def cleanup(self):
        # Call empty parent's cleanup, not empty's.
        super(empty, self).cleanup()  # pylint: disable=E1003
        # Fail test if **successful**
        image_name = self.sub_stuff['image_name']  # assume id lookup failed
        if self.parent_subtest.config['remove_after_test']:
            dkrcmd = DockerCmd(self, 'rmi', [image_name])
            mustfail(dkrcmd.execute())

    def run_tar(self, tar_command, dkr_command):
        self.copy_includes()
        # Don't feedback the output tar file into itself!
        _fd, _fn = tempfile.mkstemp(suffix='.tar',
                                    dir=os.path.dirname(self.tmpdir))
        command = "%s --file='%s'" % (tar_command, _fn)
        # Rely on any exceptions to propigate up
        utils.run(command, verbose=False)
        stats = os.stat(_fn)
        truncate_percent = self.config['truncate_percent'] / 100.0
        length = int(stats.st_size * truncate_percent)
        os.ftruncate(_fd, length)
        os.close(_fd)
        command = "cat %s | %s" % (_fn, dkr_command)
        # instance-specific namespace
        self.loginfo("Expected to fail: %s", command)
        self.sub_stuff['cmdresult'] = utils.run(command, ignore_status=True,
                                                verbose=False)

    def check_output(self):
        outputgood = output.OutputGood(self.sub_stuff['cmdresult'],
                                       ignore_error=True)
        # This is SUPPOSE to fail, fail test if it succeeds!
        self.failif(outputgood, str(outputgood))

    def check_status(self):
        successful_exit = self.sub_stuff['cmdresult'].exit_status == 0
        self.failif(successful_exit, "Unexpected command success!")
        self.loginfo("It failed as expected")

    def image_check(self):
        image_id = self.sub_stuff.get('image_id')
        self.failif(image_id is not None,
                    "Image ID '%s' successfully retrieved after expected "
                    "import failure!" % image_id)

    def copy_includes(self):
        include_dirs = self.config['include_dirs']
        for include_dir in include_dirs.split(','):
            include_dir = include_dir.strip()
            dest_dir = os.path.join(self.tmpdir, 'junk')
            self.logdebug('Copying tree at %s to %s', include_dir, dest_dir)
            shutil.copytree(include_dir, dest_dir, symlinks=True)
