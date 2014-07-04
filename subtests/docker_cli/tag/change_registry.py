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
import random
import string


class change_registry(change_tag):

    def generate_special_name(self):
        img = self.sub_stuff['image_list'][0]
        tag = img.tag
        repo = img.repo
        registry = "%s.%s.%s.%s:%s" % ("".join(random.sample(string.digits, 2)),
                                       "".join(random.sample(string.digits, 2)),
                                       "".join(random.sample(string.digits, 2)),
                                       "".join(random.sample(string.digits, 2)),
                                       "".join(random.sample(string.digits, 4)))
        registry_user = img.user
        new_img_name = DockerImage.full_name_from_component(repo, tag,
                                                            registry,
                                                            registry_user)
        return new_img_name
