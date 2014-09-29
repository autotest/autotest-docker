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
"""

from autotest.client.shared import error
from autotest.client import utils
from dockertest.subtest import SubSubtest
from dockertest.images import DockerImages
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.output import mustpass
from dockertest.dockercmd import DockerCmd
from dockertest import subtest
from dockertest import config
from dockertest import xceptions


class tag(subtest.SubSubtestCaller):

    """ SubSubtest caller """


class tag_base(SubSubtest):

    """ tag base class """

    def __init__(self, *args, **kwargs):
        super(tag_base, self).__init__(*args, **kwargs)
        self.dkrimg = DockerImages(self)
        self.sub_stuff['tmp_image_list'] = set()

    def get_images_by_name(self, full_name):
        """ :return: List of images with given name """
        return self.dkrimg.list_imgs_with_full_name(full_name)

    def prep_image(self, base_image):
        """ Tag the dockertest image to this test name """
        mustpass(DockerCmd(self, "pull", [base_image],
                           verbose=False).execute())
        subargs = [base_image, self.sub_stuff["image"]]
        tag_results = DockerCmd(self, "tag", subargs, verbose=False).execute()
        if tag_results.exit_status:
            raise xceptions.DockerTestNAError("Problems during "
                                              "initialization of"
                                              " test: %s", tag_results)

        img = self.get_images_by_name(self.sub_stuff["image"])
        self.failif(not img, "Image %s was not created."
                    % self.sub_stuff["image"])
        self.sub_stuff['image_list'] = img

    def initialize(self):
        super(tag_base, self).initialize()
        config.none_if_empty(self.config)
        self.dkrimg.gen_lower_only = self.config['gen_lower_only']
        new_img_name = self.dkrimg.get_unique_name()
        self.sub_stuff["image"] = new_img_name
        base_image = DockerImage.full_name_from_defaults(self.config)
        self.prep_image(base_image)

    def complete_docker_command_line(self):
        """ :return: tag subargs using new_image_name """
        force = self.config["tag_force"]

        cmd = []
        if force:
            cmd.append("-f")

        cmd.append(self.sub_stuff["image"])
        cmd.append(self.sub_stuff["new_image_name"])
        self.sub_stuff["tag_cmd"] = cmd
        return cmd

    def run_once(self):
        super(tag_base, self).run_once()
        subargs = self.complete_docker_command_line()
        self.sub_stuff["cmdresult"] = DockerCmd(self, 'tag', subargs).execute()

    def postprocess(self):
        super(tag_base, self).postprocess()
        if self.config["docker_expected_result"] == "PASS":
            # Raise exception if problems found
            OutputGood(self.sub_stuff['cmdresult'])
            self.failif(self.sub_stuff['cmdresult'].exit_status != 0,
                        "Non-zero tag exit status: %s"
                        % self.sub_stuff['cmdresult'])

            img = self.get_images_by_name(self.sub_stuff["new_image_name"])
            # Needed for cleanup
            self.sub_stuff['image_list'] += img
            self.failif(len(img) < 1,
                        "Failed to look up tagted image ")

        elif self.config["docker_expected_result"] == "FAIL":
            chck = OutputGood(self.sub_stuff['cmdresult'], ignore_error=True)
            exit_code = self.sub_stuff['cmdresult'].exit_status
            self.failif(not chck or not exit_code,
                        "Zero tag exit status: Command should fail due to"
                        " wrong command arguments.")
        else:
            self.failif(True, "Improper 'docker_expected_result' value %s"
                        % self.config["docker_expected_result"])

    def cleanup(self):
        super(tag_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['remove_after_test'] and 'image_list' in self.sub_stuff:
            for image in self.sub_stuff["image_list"]:
                self.logdebug("Removing image %s", image.full_name)
                try:
                    self.dkrimg.remove_image_by_full_name(image.full_name)
                except error.CmdError, exc:
                    err = exc.result_obj.stderr
                    if "tagged in multiple repositories" not in err:
                        raise
                self.loginfo("Successfully removed test image: %s",
                             image.full_name)
            for image in self.sub_stuff['tmp_image_list']:
                image = self.get_images_by_name(image)
                if image:
                    self.logdebug("Removing image %s", image[0].full_name)
                    self.dkrimg.remove_image_by_full_name(image[0].full_name)
                    self.loginfo("Successfully removed test image: %s",
                                 image[0].full_name)


class change_tag(tag_base):

    """
    1. tag testing image with different tag (keep the name, change only tag)
    2. verify it worked well
    """

    def generate_special_name(self):
        """ keep the name, only get unique tag """
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
        while self.get_images_by_name(new_img_name):
            new_img_name = self.generate_special_name()

        self.sub_stuff["new_image_name"] = new_img_name


class double_tag(change_tag):

    """
    1. tag testing image with different tag (keep the name, change only tag)
    2. do the same and expect failure
    """

    def initialize(self):
        super(double_tag, self).initialize()
        # Tag it for the first time
        self.sub_stuff['tmp_image_list'].add(self.sub_stuff["new_image_name"])
        mustpass(DockerCmd(self, 'tag', self.complete_docker_command_line(),
                           verbose=False).execute())


class double_tag_force(double_tag):

    """ Same as ``double_tag`` only this time use `--force` and expect pass """
