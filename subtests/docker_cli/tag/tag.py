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
from dockertest.output import DockerVersion
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
        self._expect_pass = True

    def expect_pass(self, set_to=None):
        """
         Most of the time we expect our 'docker tag' command to succeed.
         This method can be used (as a setter) to set an explicit expectation
         or (as a getter) when checking results.
        """
        if set_to is not None:
            self._expect_pass = set_to
        return self._expect_pass

    def get_images_by_name(self, full_name):
        """ :return: List of images with given name """
        return self.dkrimg.list_imgs_with_full_name(full_name)

    def prep_image(self, base_image):
        """ Tag the dockertest image to this test name """
        mustpass(DockerCmd(self, "pull", [base_image]).execute())
        subargs = [base_image, self.sub_stuff["image"]]
        tag_results = DockerCmd(self, "tag", subargs).execute()
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
        cmd = []
        if 'force_tag' in self.sub_stuff and self.sub_stuff['force_tag']:
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
        expect_pass = self.expect_pass()
        OutputGood(self.sub_stuff['cmdresult'], ignore_error=not expect_pass)
        if expect_pass:
            # Raise exception if problems found
            self.failif_ne(self.sub_stuff['cmdresult'].exit_status, 0,
                           "Non-zero tag exit status: %s"
                           % self.sub_stuff['cmdresult'])

            img = self.get_images_by_name(self.sub_stuff["new_image_name"])
            # Needed for cleanup
            self.sub_stuff['image_list'] += img
            self.failif(len(img) < 1,
                        "Failed to look up tagged image ")

        else:
            self.failif(self.sub_stuff['cmdresult'].exit_status == 0,
                        "Was expecting tag command to fail, but it exited OK")

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
            for image_name in self.sub_stuff['tmp_image_list']:
                image = self.get_images_by_name(image_name)
                if image:
                    self.logdebug("Removing tmp image %s", image[0].full_name)
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
        # Tag it for the first time. This should pass...
        self.sub_stuff['tmp_image_list'].add(self.sub_stuff["new_image_name"])
        mustpass(DockerCmd(self, 'tag',
                           self.complete_docker_command_line()).execute())
        # On docker 1.10, the second tag should pass. On < 1.10, fail.
        try:
            DockerVersion().require_server("1.10")
            self.expect_pass(True)
        except xceptions.DockerTestNAError:
            self.expect_pass(False)


class double_tag_force(double_tag):

    """ Same as ``double_tag`` only this time use `--force` and expect pass """

    def initialize(self):
        super(double_tag_force, self).initialize()
        # Difference from parent is that we use --force, and should pass
        self.sub_stuff['force_tag'] = True
        self.expect_pass(True)
