r"""
Summary
----------

Test output of docker tag command

Operational Summary
----------------------

#. Make new image name.
#. tag changes.
#. check if tagged image exists.
#. remote tagged image from local repo.

Prerequisites
-------------------
None

Configuration
-----------------
*  ``tag_force`` specifies use of ``--force`` option
*  The ``tag_repo_name_prefix`` option has random characters appended
   before it is used for tagging.
*  ``docker_expected_result`` option allows changing between positive
   and negative testing.
"""

import time
from autotest.client.shared import error
from autotest.client import utils
from dockertest.subtest import SubSubtest
from dockertest.images import DockerImages
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest import subtest
from dockertest import config
from dockertest import xceptions


class tag(subtest.SubSubtestCaller):
    pass


class tag_base(SubSubtest):

    def check_image_exists(self, full_name):
        di = DockerImages(self.parent_subtest)
        return di.list_imgs_with_full_name(full_name)

    def prep_image(self, base_image):
        pull_results = DockerCmd(self, "pull",
                                 [base_image]).execute()
        if pull_results.exit_status:
            raise xceptions.DockerTestNAError("Problem pulling"
                                              "base image %s for test"
                                              % base_image)
        subargs = [base_image, self.sub_stuff["image"]]
        tag_results = DockerCmd(self, "tag", subargs).execute()
        if tag_results.exit_status:
            raise xceptions.DockerTestNAError("Problems during "
                                              "initialization of"
                                              " test: %s", tag_results)

        im = self.check_image_exists(self.sub_stuff["image"])
        self.sub_stuff['image_list'] = im

    def initialize(self):
        super(tag_base, self).initialize()
        config.none_if_empty(self.config)

        di = DockerImages(self.parent_subtest)
        di.gen_lower_only = self.config['gen_lower_only']
        new_img_name = di.get_unique_name()
        # Make sure there are UPPER chars in the name (not gen_lower_only)
        if (not self.config['gen_lower_only'] and
                (new_img_name.lower() == new_img_name)):
            new_img_name = di.get_unique_name("UPPER")

        self.sub_stuff["image"] = new_img_name
        base_image = DockerImage.full_name_from_defaults(self.config)
        self.prep_image(base_image)

    def complete_docker_command_line(self):
        force = self.config["tag_force"]

        cmd = []
        if force == "yes":
            cmd.append("-f")

        cmd.append(self.sub_stuff["image"])
        cmd.append(self.sub_stuff["new_image_name"])
        self.sub_stuff["tag_cmd"] = cmd
        return cmd

    def run_once(self):
        super(tag_base, self).run_once()
        dkrcmd = AsyncDockerCmd(self, 'tag',
                                self.complete_docker_command_line())
        self.loginfo("Executing background command: %s" % dkrcmd)
        dkrcmd.execute()
        while not dkrcmd.done:
            self.loginfo("tagging...")
            time.sleep(3)
        self.sub_stuff["cmdresult"] = dkrcmd.wait()

    def postprocess(self):
        super(tag_base, self).postprocess()
        if self.config["docker_expected_result"] == "PASS":
            # Raise exception if problems found
            OutputGood(self.sub_stuff['cmdresult'])
            self.failif(self.sub_stuff['cmdresult'].exit_status != 0,
                        "Non-zero tag exit status: %s"
                        % self.sub_stuff['cmdresult'])

            im = self.check_image_exists(self.sub_stuff["new_image_name"])
            # Needed for cleanup
            self.sub_stuff['image_list'] += im
            self.failif(len(im) < 1,
                        "Failed to look up tagted image ")

        elif self.config["docker_expected_result"] == "FAIL":
            og = OutputGood(self.sub_stuff['cmdresult'], ignore_error=True)
            es = self.sub_stuff['cmdresult'].exit_status == 0
            self.failif(not og or not es,
                        "Zero tag exit status: Command should fail due to"
                        " wrong command arguments.")

    def cleanup(self):
        super(tag_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['remove_after_test'] and 'image_list' in self.sub_stuff:
            for image in self.sub_stuff["image_list"]:
                di = DockerImages(self.parent_subtest)
                self.logdebug("Removing image %s", image.full_name)
                try:
                    di.remove_image_by_full_name(image.full_name)
                except error.CmdError, e:
                    err = e.result_obj.stderr
                    if "tagged in multiple repositories" not in err:
                        raise
                self.loginfo("Successfully removed test image: %s",
                             image.full_name)


class change_tag(tag_base):

    def generate_special_name(self):
        img = self.sub_stuff['image_list'][0]
        _tag = "%s_%s" % (img.tag, utils.generate_random_string(8))
        if self.config['gen_lower_only']:
            _tag = _tag.lower()
        else:
            _tag += '_UP'  # guarantee some upper-case
        repo = img.repo
        registry = img.repo_addr
        registry_user = img.user
        new_img_name = DockerImage.full_name_from_component(repo,
                                                            _tag,
                                                            registry,
                                                            registry_user)
        return new_img_name

    def initialize(self):
        super(change_tag, self).initialize()

        new_img_name = self.generate_special_name()
        while self.check_image_exists(new_img_name):
            new_img_name = self.generate_special_name()

        self.sub_stuff["new_image_name"] = new_img_name
