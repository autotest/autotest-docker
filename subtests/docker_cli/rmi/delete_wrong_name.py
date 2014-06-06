"""
Test output of docker rmi command

docker rmi full_name

1. Find full_name (tag) which not exists.
2. Try to remove new full_name
3. Check if rmi command failed
"""
from autotest.client import utils
from rmi import rmi_base
from dockertest.output import OutputGood

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


class delete_wrong_name(rmi_base):
    config_section = 'docker_cli/rmi/delete_wrong_name'

    def initialize(self):
        super(delete_wrong_name, self).initialize()

        name_prefix = self.config["rmi_repo_tag_name_prefix"]

        rand_data = utils.generate_random_string(5).lower()
        self.sub_stuff["rand_data"] = rand_data
        im_name = "%s_%s" % (name_prefix, rand_data)
        im = self.check_image_exists(im_name)
        while im != []:
            rand_data = utils.generate_random_string(5)
            self.sub_stuff["rand_data"] = rand_data
            im_name = "%s_%s" % (name_prefix, rand_data)
            im = self.check_image_exists(im_name)

        self.sub_stuff["image_name"] = im_name
        # Private to this instance, outside of __init__

    def postprocess(self):
        super(delete_wrong_name, self).postprocess()
        # Raise exception if problems found
        OutputGood(self.sub_stuff['cmdresult'], ignore_error=True)
        if self.config["docker_expected_result"] == "FAIL":
            self.failif(self.sub_stuff['cmdresult'].exit_status == 0,
                        "Zero rmi exit status: Command should fail due to"
                        " wrong image name.")
