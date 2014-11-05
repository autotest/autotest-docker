"""
Sub-subtest module used by dockerimport test

1. Create an empty tar file
2. Pipe empty file into docker import command
3. Check imported image is available
"""

import os
from autotest.client import utils
from dockertest import output
from dockertest.subtest import SubSubtest
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImages, DockerImage


class empty(SubSubtest):

    def initialize(self):
        super(empty, self).initialize()
        di = DockerImages(self.parent_subtest)
        suffix = self.config.get('image_name_postfix')
        image_name_tag = di.get_unique_name(suffix=suffix)
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
        docker_command = DockerCmd(self, 'import', subargs)
        self.run_tar(tar_command, docker_command.command)

    def postprocess(self):
        super(empty, self).postprocess()
        # name parameter cannot contain tag, don't assume prefix/postfix
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
            dkrcmd = DockerCmd(self, 'rmi', [self.sub_stuff['image_name_tag']])
            cmdresult = dkrcmd.execute()
            if cmdresult.exit_status != 0:
                self.logwarning("Cleanup command failed: %s" % cmdresult)

    def run_tar(self, tar_command, dkr_command):
        command = "%s | %s" % (tar_command, dkr_command)
        # Free, instance-specific namespace
        self.logdebug("Command line: %s" % command)
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
        self.failif(not condition, ("Non-zero exit status: %s"
                                    % self.sub_stuff['cmdresult']))

    def lookup_image_id(self, image_name, image_tag):
        di = DockerImages(self.parent_subtest)
        fqin = DockerImage.full_name_from_component(image_name, image_tag)
        imglst = di.list_imgs_with_full_name(fqin)
        try:
            # Don't care about duplicate ID's
            return imglst[0].long_id
        except IndexError:
            return None  # expected by some sub-subtests
