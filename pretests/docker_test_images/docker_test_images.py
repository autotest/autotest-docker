r"""
Summary
---------

Pre-testing pulling and listing of test image(s) into sysinfo results

Operational Summary
----------------------

#. Parse the default test image into FQIN format
#. Pull the default, and any configured ``extra_fqins_csv`` images
#. Log a listing of all current images to debug and a sysinfo file
#. Optionally, update ``config_defaults/defaults.ini`` (if it exists)
   to preserve all pulled images.  Configured by ``update_defaults_ini``
   option (default: False)

Prerequisites
---------------

The default image and any ``extra_fqins_csv`` images exist and are pull-able
within the testing timeout period.  If it is to be updated with pulled images,
the file ``config_defaults/defaults.ini`` must exist.
"""

import os.path
from dockertest.subtest import Subtest
from dockertest.images import DockerImages
from dockertest.dockercmd import DockerCmd
from dockertest.config import get_as_list
from dockertest.config import CONFIGCUSTOMS
from dockertest.config import ConfigSection


class docker_test_images(Subtest):
    """Pull, then log a listing of docker images present on system"""

    def initialize(self):
        super(docker_test_images, self).initialize()
        self.stuff['di'] = di = DockerImages(self)
        extra_fqins_csv = self.config.get('extra_fqins_csv', '')
        update_defaults_ini = self.config.get('update_defaults_ini', False)
        self.stuff['defaults_ini'] = os.path.join(CONFIGCUSTOMS,
                                                  'defaults.ini')
        defaults_ini_exists = os.path.isfile(self.stuff['defaults_ini'])
        self.stuff['update'] = update_defaults_ini and defaults_ini_exists
        self.stuff['fqins'] = [di.default_image] + get_as_list(extra_fqins_csv)

    def run_once(self):
        super(docker_test_images, self).run_once()
        for fqin in self.stuff['fqins']:
            self.loginfo("Pulling %s", fqin)
            # TODO: Support pulling/verifying with atomic command
            DockerCmd(self, 'pull', [fqin]).execute()

    def postprocess(self):
        super(docker_test_images, self).postprocess()
        # File in top-level 'results/default/sysinfo' directory
        with open(os.path.join(self.job.sysinfo.sysinfodir,
                               'docker_images'), 'wb') as info_file:
            for img in self.stuff['di'].list_imgs():
                info_file.write("%s\n" % str(img))
                self.loginfo(str(img))
        # Hopefully not a TOCTOU race with initialize()
        if self.stuff['update'] and self.stuff['fqins']:
            # These /are/ the customized defaults, don't re-default them
            cfgsec = ConfigSection(dict(), 'DEFAULTS')
            # This may not exist
            if cfgsec.has_option('preserve_fqins'):
                preserve_fqins = get_as_list(cfgsec.get('preserve_fqins'))
            else:
                preserve_fqins = []
            self.logdebug("Old preserve_fqins: %s", preserve_fqins)
            # Update the existing list
            preserve_fqins += self.stuff['fqins']
            # Convert back to CSV, value still in memory only
            cfgsec.set('preserve_fqins', ",".join(preserve_fqins))
            # This will get picked up when next test executes
            cfgsec.merge_write(open(self.stuff['defaults_ini'], 'wb'))
            self.loginfo("Updated preserve_fqins: %s",
                         cfgsec.get('preserve_fqins'))
