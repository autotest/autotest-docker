r"""
Summary
---------

Pre-testing pulling and listing of test image(s) into sysinfo results

Operational Summary
----------------------

#. Parse the default test image into FQIN format
#. Pull the default, and any configured ``extra_fqins_csv`` images
#. Build any ``build_dockerfile`` w/ ``build_name`` images.
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
from dockertest.subtest import SubSubtestCaller
from dockertest.subtest import SubSubtest
from dockertest.images import DockerImages
from dockertest.dockercmd import DockerCmd
from dockertest.config import Config
from dockertest.config import get_as_list
from dockertest.config import CONFIGCUSTOMS
from dockertest.config import ConfigSection
from dockertest.output.validate import mustpass


class docker_test_images(SubSubtestCaller):
    """
    Pull, optionally build, log present image details, then update defaults.ini
    """

    def initialize(self):
        super(docker_test_images, self).initialize()
        # Keep it simple, just use/store everything in this instance
        self.stuff['di'] = di = DockerImages(self)
        extra_fqins_csv = self.config.get('extra_fqins_csv', '')
        update_defaults_ini = self.config.get('update_defaults_ini', False)
        self.stuff['defaults_ini'] = os.path.join(CONFIGCUSTOMS,
                                                  'defaults.ini')
        defaults_ini_exists = os.path.isfile(self.stuff['defaults_ini'])
        self.stuff['update'] = update_defaults_ini and defaults_ini_exists
        self.stuff['fqins'] = [di.default_image] + get_as_list(extra_fqins_csv)
        # Optional, could be {None: None}
        self.stuff['build'] = {self.config.get('build_name'):
                               self.config.get('build_dockerfile')}

    def postprocess(self):
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
            # config.merge_write() can't work with DEFAULTS
            for key, value in Config.defaults_.items():
                cfgsec.set(key, value)
            # This may not exist
            if cfgsec.has_option('preserve_fqins'):
                preserve_fqins = set(get_as_list(cfgsec.get('preserve_fqins')))
            else:
                preserve_fqins = set([])
            self.logdebug("Old preserve_fqins: %s", preserve_fqins)
            # Update the existing list
            preserve_fqins |= set(self.stuff['fqins'])
            # Convert back to CSV, value still in memory only
            cfgsec.set('preserve_fqins', ",".join(preserve_fqins))
            self.loginfo("Updated preserve_fqins: %s",
                         cfgsec.get('preserve_fqins'))
            # This will get picked up when next test executes
            cfgsec.write(open(self.stuff['defaults_ini'], 'wb'))
            # Be kind to anyone debugging the contents
            msg = "\n# preserve_fqins modified by %s\n" % self.config_section
            open(self.stuff['defaults_ini'], 'ab').write(msg)
        super(docker_test_images, self).postprocess()


class puller(SubSubtest):
    """Pull the default docker image if not present on system"""

    def run_once(self):
        super(puller, self).run_once()
        # Using parent instance's stuff, not sub_stuff for simplicity
        for fqin in self.parent_subtest.stuff['fqins']:
            if not fqin:
                continue
            self.loginfo("Pulling %s", fqin)
            # TODO: Support pulling/verifying with atomic command
            mustpass(DockerCmd(self, 'pull', [fqin]).execute())


class builder(SubSubtest):
    """Build ``build_dockerfile`` with tag ``build_name`` if defined"""

    def run_once(self):
        super(builder, self).run_once()
        if None in self.parent_subtest.stuff['build']:
            return
        subopts = get_as_list(self.config.get('build_opts_csv', []))
        stuff = self.parent_subtest.stuff
        # Someday we might support building more than one
        for name, dockerfile in stuff['build'].items():
            this_subopts = subopts + ['-t', name, dockerfile]
            mustpass(DockerCmd(self, 'build', this_subopts).execute())
            stuff['fqins'] += stuff['build'].keys()
