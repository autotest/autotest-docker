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

import os, os.path, shutil, time, logging
from autotest.client import utils
from dockertest import subtest
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd, NoFailDockerCmd

try:
    import docker
    DOCKERAPI = True
except ImportError:
    DOCKERAPI = False

class build(subtest.Subtest):
    version = "0.0.2"
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
        bb_dst = os.path.join(self.srcdir, 'busybox')
        shutil.copy(self.config['busybox_path'], bb_dst)

    def initialize(self):
        super(build, self).initialize()
        condition = self.config['build_timeout_seconds'] >= 10
        self.failif(not condition, "Config option build_timeout_seconds "
                                   "is probably too short")
        # FIXME: Need a standard way to do this
        image_name_tag = ("%s%s%s"
                          % (self.config['image_name_prefix'],
                             utils.generate_random_string(4),
                             self.config['image_name_postfix']))
        image_name, image_tag = image_name_tag.split(':', 1)
        self.config['image_name_tag'] = image_name_tag
        self.config['image_name'] = image_name
        self.config['image_tag'] = image_tag
        # TODO: Supply 'FROM' contents to Dockerfile (See Dockerfile)

    def run_once(self):
        super(build, self).run_once()
        subargs = [self.config['docker_build_options'],
                   "-t", self.config['image_name_tag'],
                   self.srcdir]
        # Don't really need async here, just exercizing class
        dkrcmd = AsyncDockerCmd(self, 'build', subargs,
                                self.config['build_timeout_seconds'])
        self.loginfo("Executing background command: %s" % dkrcmd)
        dkrcmd.execute()
        while not dkrcmd.done:
            self.loginfo("Building...")
            time.sleep(3)
        self.config["cmdresult"] = dkrcmd.wait()

    def postprocess(self):
        super(build, self).postprocess()
        # Raise exception if problems found
        OutputGood(self.config['cmdresult'])
        self.failif(self.config['cmdresult'].exit_status != 0,
                    "Non-zero build exit status: %s"
                    % self.config['cmdresult'])
        image_name = self.config['image_name']
        image_tag = self.config['image_tag']
        self.config['image_id'] = self.lookup_image_id(image_name, image_tag)
        self.failif(self.config['image_id'] is None,
                    "Failed to look up image ID from build")

    def cleanup(self):
        super(build, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if (self.config['try_remove_after_test'] and
                                             self.config.has_key('image_id')):
            NoFailDockerCmd(self, "rmi", self.config['image_id'])
            self.loginfo("Successfully removed test image")

    def lookup_image_id(self, image_name, image_tag):
        # FIXME: Need a standard way to do this
        image_id = None
        # Any API failures must not be fatal
        if DOCKERAPI:
            client = docker.Client()
            results = client.images(name=image_name)
            image = None
            if len(results) == 1:
                image = results[0]
                # Could be unicode strings
                if ((str(image['Repository']) == image_name) and
                    (str(image['Tag']) == image_tag)):
                    image_id = image.get('Id')
            if ((image_id is None) or (len(image_id) < 12)):
                logging.error("Could not lookup image %s:%s Id using "
                              "docker python API Data: '%s'",
                              image_name, image_tag, str(image))
                image_id = None
        # Don't have DOCKERAPI or API failed (still need image ID)
        if image_id is None:
            # Blah! This only works with name, not tag :S
            subargs = ['--quiet', image_name]
            dkrcmd = NoFailDockerCmd(self, 'images', subargs)
            # fail -> raise exception
            cmdresult = dkrcmd.execute()
            # Not found, exits with 0 and no output
            # Multiple found, exits with all IDs + no tags mapping :S
            stdout_strip = cmdresult.stdout.strip()
            # TODO: Better image ID validity check?
            if len(stdout_strip) == 12:
                image_id = stdout_strip
            else:
                self.loginfo("Error retrieving image id, unexpected length")
        if image_id is not None:
            self.loginfo("Found image Id '%s'", image_id)
        return image_id
