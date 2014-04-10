"""
Test output of docker tag command

docker tag full_name new_name

Initialize
1. Make new image name.
run_once
2. tag changes.
postprocess
3. check if tagged image exists.
clean
4. remote tagged image from local repo.
"""

from tag import change_tag
from dockertest.images import DockerImage
from autotest.client import utils

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


class change_repository(change_tag):
    config_section = 'docker_cli/commit/change_repository'

    def generate_special_name(self):
        name_prefix = self.config["tag_repo_name_prefix"]
        img = self.sub_stuff['image_list'][0]
        tag = img.tag
        repo = "%s_%s" % (name_prefix, utils.generate_random_string(8))
        registry = img.repo_addr
        registry_user = img.user
        new_img_name = DockerImage.full_name_from_component(repo, tag,
                                                            registry,
                                                            registry_user)
        return new_img_name
