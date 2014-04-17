"""
Test run of docker build command

1. Copy source files + static busybox to srcdir if necessary
2. Verify timeout isn't too short
3. Start build in srcdir
4. Check build exit code, make sure image exists
5. Optionally remove built image
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import os, os.path, shutil, time
from autotest.client import utils
from dockertest import subtest
from dockertest.images import DockerImages
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.dockercmd import NoFailDockerCmd

class build(subtest.Subtest):
    config_section = 'docker_cli/build'

    def setup(self):
        super(build, self).setup()
        for filename in self.config['source_files'].split(','):
            # bindir is location of this module
            src = os.path.join(self.bindir, filename)
            # srcdir is recreated if doesn't exist or if test version changes
            dst = os.path.join(self.srcdir, filename)
            shutil.copy(src, dst)
        # Must exist w/in directory holding Dockerfile
        from httplib import HTTPConnection
        import logging
        url = self.config['busybox_url'].split("/", 1)
        logging.debug("Downloading busybox from http://%s%s location",
                      url[0], url[1])
        url[1] = "/" + url[1]     # Add the removed '/'
        conn = HTTPConnection(url[0])
        conn.request("GET", url[1])
        resp = conn.getresponse()
        data = resp.read()
        busybox = os.open(os.path.join(self.srcdir, 'busybox'),
                          os.O_WRONLY | os.O_CREAT, 0755)
        os.write(busybox, data)
        os.close(busybox)

    def initialize(self):
        super(build, self).initialize()
        condition = self.config['build_timeout_seconds'] >= 10
        self.failif(not condition, "Config option build_timeout_seconds "
                                   "is probably too short")
        di = DockerImages(self)
        image_name_tag = di.get_unique_name(self.config['image_name_prefix'],
                                            self.config['image_name_postfix'])
        image_name, image_tag = image_name_tag.split(':', 1)
        self.stuff['image_name_tag'] = image_name_tag
        self.stuff['image_name'] = image_name
        self.stuff['image_tag'] = image_tag
        # Must build from a base-image, import an empty one
        tarball = open(os.path.join(self.bindir, 'empty_base_image.tar'), 'rb')
        dc = NoFailDockerCmd(self, 'import', ["-", "empty_base_image"])
        dc.execute(stdin=tarball)

    def run_once(self):
        super(build, self).run_once()
        subargs = [self.config['docker_build_options'],
                   "-t", self.stuff['image_name_tag'],
                   self.srcdir]
        # Don't really need async here, just exercizing class
        dkrcmd = AsyncDockerCmd(self, 'build', subargs,
                                self.config['build_timeout_seconds'])
        self.loginfo("Executing background command: %s" % dkrcmd)
        dkrcmd.execute()
        while not dkrcmd.done:
            self.loginfo("Building...")
            time.sleep(3)
        self.stuff["cmdresult"] = dkrcmd.wait()

    def postprocess(self):
        super(build, self).postprocess()
        # Raise exception if problems found
        OutputGood(self.stuff['cmdresult'])
        self.failif(self.stuff['cmdresult'].exit_status != 0,
                    "Non-zero build exit status: %s"
                    % self.stuff['cmdresult'])
        image_name = self.stuff['image_name']
        image_tag = self.stuff['image_tag']
        di = DockerImages(self)
        imgs = di.list_imgs_with_full_name_components(repo=image_name,
                                                      tag=image_tag)
        self.failif(len(imgs) < 1, "Test image build result was not found")
        self.stuff['image_id'] = imgs[0].long_id  # assume first one is match
        self.failif(self.stuff['image_id'] is None,
                    "Failed to look up image ID from build")
        self.loginfo("Found image: %s", imgs[0].full_name)

    def cleanup(self):
        super(build, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if (self.config['try_remove_after_test'] and
                                             self.stuff.has_key('image_id')):
            di = DockerImages(self)
            di.remove_image_by_id(self.stuff['image_id'])
            di.remove_image_by_full_name("empty_base_image")
            self.loginfo("Successfully removed test images")
        else:
            self.loginfo("NOT removing image")
