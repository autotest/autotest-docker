"""
Test output of docker rmi command

docker rmi full_name

1. Create new image with full_name (tag) from image (base_image)
2. Try to remove new full_name
3. Check if tag still exits.
"""

from autotest.client import utils
from rmi import rmi_base
from dockertest.dockercmd import DockerCmd
from dockertest.xceptions import DockerTestNAError

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

class only_tag(rmi_base):
    config_section = 'docker_cli/rmi/only_tag'

    def initialize(self):
        super(only_tag, self).initialize()

        name_prefix = self.config["rmi_repo_tag_name_prefix"]

        rand_data = utils.generate_random_string(5).lower()
        self.sub_stuff["rand_data"] = rand_data
        im_name = "%s_%s" % (name_prefix, rand_data)
        im = self.check_image_exists(im_name)
        while im != []:
            rand_data = utils.generate_random_string(5).lower()
            self.sub_stuff["rand_data"] = rand_data
            im_name = "%s_%s" % (name_prefix, rand_data)
            im = self.check_image_exists(im_name)

        self.sub_stuff["image_name"] = im_name
        # Private to this instance, outside of __init__

        prep_changes = DockerCmd(self.parent_subtest, "tag",
                                 [self.parent_subtest.stuff["base_image"],
                                  self.sub_stuff["image_name"]],
                                 self.config['docker_rmi_timeout'])

        results = prep_changes.execute()
        if results.exit_status:
            raise DockerTestNAError("Problems during initialization of"
                                    " test: %s", results)
