"""
Sub-subtest module used by dockerimport test
"""

from autotest.client import utils
import tempfile, os, os.path, shutil
from empty import empty

class truncated(empty):

    def cleanup(self):
        repo = self.config.get('repo')
        if repo is not None:
            docker_command = self.test.config['docker_path']
            docker_options = self.test.config['docker_options']
            command = ("%s %s rmi %s" % (docker_command, docker_options,
                                         self.config['repo']))
            cmdresult = utils.run(command, ignore_status=True)
            self.test.failif(cmdresult.exit_status == 0,
                            "Unexpected image removalsucceeded: %s" %
                            str(cmdresult))
        # expected repo not to exist!

    def run_tar(self, tar_command, dkr_command):
        self.copy_includes()
        # Don't feedback the output tar file into itself!
        _fd, _fn = tempfile.mkstemp(suffix='.tar',
                                    dir=os.path.dirname(self.tmpdir))
        command = "%s --file='%s'" % (tar_command, _fn)
        # Rely on any exceptions to propigate up
        utils.run(command)
        stats = os.stat(_fn)
        truncate_percent = self.config['truncate_percent'] / 100.0
        length = int(stats.st_size * truncate_percent)
        os.ftruncate(_fd, length)
        os.close(_fd)
        command = "cat %s | %s" % (_fn, dkr_command)
        # instance-specific namespace
        self.config['cmdresult'] = utils.run(command, ignore_status=True)
        self.test.logdebug("Expected to fail: %s", self.config['cmdresult'])

    def check_status(self):
        condition = self.config['cmdresult'].exit_status == 0
        self.test.failif(condition, "Unexpected command success")

    def try_check_images(self):
        pass  # image checkd in cleanup

    def copy_includes(self):
        include_dirs = self.config['include_dirs']
        for include_dir in include_dirs.split(','):
            include_dir = include_dir.strip()
            self.logdebug('Copying tree at %s to repo tmp root', include_dir)
            shutil.copytree(include_dir,
                            os.path.join(self.tmpdir, 'junk'), symlinks=True)
