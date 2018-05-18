"""
Test output of docker rmi command

docker rmi full_name

1. Find full_name (tag) which not exists.
2. Try to remove new full_name
3. Check if rmi command failed
"""
from autotest.client import utils
from dockertest.images import DockerImages
from rmi import rmi_base


class delete_wrong_name(rmi_base):
    config_section = 'docker_cli/rmi/delete_wrong_name'

    def initialize(self):
        super(delete_wrong_name, self).initialize()

        rand_data = utils.generate_random_string(5).lower()
        self.sub_stuff["rand_data"] = rand_data
        im_name = DockerImages(self).get_unique_name()

        self.sub_stuff["image_name"] = im_name
        # Private to this instance, outside of __init__
