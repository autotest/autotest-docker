"""
Sub-subtest module used by dockerimport test

1. Create an empty tar file
2. Pipe empty file into docker import command
3. Check imported image is available
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import os, logging
from autotest.client import utils
from dockertest import output
from dockertest.subtest import SubSubtest
from dockertest.dockercmd import DockerCmd, NoFailDockerCmd

try:
    import docker
    DOCKERAPI = True
except ImportError:
    DOCKERAPI = False

class empty(SubSubtest):

    def initialize(self):
        super(empty, self).initialize()
        # FIXME: Need a standard way to do this
        image_name_tag = ("%s%s%s"
                          % (self.parent_subtest.config['image_name_prefix'],
                             utils.generate_random_string(4),
                             self.parent_subtest.config['image_name_postfix']))
        image_name, image_tag = image_name_tag.split(':', 1)
        self.sub_stuff['image_name_tag'] = image_name_tag
        self.sub_stuff['image_name'] = image_name
        self.sub_stuff['image_tag'] = image_tag

    def run_once(self):
        super(empty, self).run_once()
        os.chdir(self.tmpdir)
        tar_command = self.config['tar_command']
        tar_options = self.config['tar_options']
        tar_command = "%s %s" % (tar_command, tar_options)
        subargs = ['-', self.sub_stuff['image_name_tag']]
        docker_command = DockerCmd(self.parent_subtest, 'import', subargs)
        self.run_tar(tar_command, str(docker_command))

    def postprocess(self):
        super(empty, self).postprocess()
        # name parameter cannot contain tag, don't assume prefix/postfix content
        self.check_output()
        self.check_status()
        image_id = self.lookup_image_id(self.sub_stuff['image_name'],
                                        self.sub_stuff['image_tag'])
        self.sub_stuff['image_id'] = image_id
        self.image_check()

    def image_check(self):
        # Fail subsubtest if...
        result_id = self.sub_stuff['result_id']
        image_id = self.sub_stuff['image_id']
        self.logdebug("Resulting ID: %s", result_id)
        result_contains_id = result_id.count(image_id)
        self.failif(not result_contains_id,
                    "Repository Id's do not match (%s,%s)"
                    % (result_id, image_id))

    def cleanup(self):
        super(empty, self).cleanup()
        if self.parent_subtest.config['try_remove_after_test']:
            dkrcmd = NoFailDockerCmd(self.parent_subtest, 'rmi',
                                     [self.sub_stuff['result_id']])
            dkrcmd.execute()

    def run_tar(self, tar_command, dkr_command):
        command = "%s | %s" % (tar_command, dkr_command)
        # Free, instance-specific namespace
        cmdresult = utils.run(command, ignore_status=True, verbose=False)
        self.sub_stuff['cmdresult'] = cmdresult
        self.loginfo("Command result: %s", cmdresult.stdout.strip())
        self.sub_stuff['result_id'] = cmdresult.stdout.strip()

    def check_output(self):
        outputgood = output.OutputGood(self.sub_stuff['cmdresult'],
                                       ignore_error=True)
        self.failif(not outputgood, str(outputgood))

    def check_status(self):
        condition = self.sub_stuff['cmdresult'].exit_status == 0
        self.failif(not condition, "Non-zero exit status")

    def lookup_image_id(self, image_name, image_tag):
        # FIXME: We need a standard way to do this
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
            subargs = ['--quiet', image_name]
            dkrcmd = NoFailDockerCmd(self.parent_subtest, 'images', subargs)
            # fail -> raise exception
            cmdresult = dkrcmd.execute()
            stdout_strip = cmdresult.stdout.strip()
            # TODO: Better image ID validity check?
            if len(stdout_strip) == 12:
                image_id = stdout_strip
            else:
                self.loginfo("Error retrieving image id, unexpected length")
        if image_id is not None:
            self.loginfo("Found image Id '%s'", image_id)
        return image_id
