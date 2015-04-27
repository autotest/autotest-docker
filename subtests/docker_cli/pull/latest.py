"""
Verify pulling :latest tagged image also pulls down numbered
"""

from dockertest.images import DockerImage
from dockertest.images import DockerImages
from pull import pull_base


class NoTagDockerImage(DockerImage):
    """Completely ignore tag of all images, don't use for compare"""

    __eq__ = DockerImage.cmp_greedy_full_name

    def __init__(self, repo, tag, long_id, created, size,
                 repo_addr=None, user=None):
        """Forces tag parameter to be passed as None"""
        super(NoTagDockerImage, self).__init__(repo=repo, tag=None,
                                               long_id=long_id,
                                               created=created,
                                               size=size,
                                               repo_addr=repo_addr,
                                               user=user)

    @classmethod
    def full_name_from_component(cls, repo, tag=None,
                                 repo_addr=None, user=None):
        """Forces tag parameter to be passed as None"""
        fnfc = super(NoTagDockerImage, cls).full_name_from_component
        return fnfc(repo=repo, tag=None, repo_addr=repo_addr, user=user)


class NoTagDockerImages(DockerImages):
    """Completely disregards image tags"""

    DICLS = NoTagDockerImage
    verbose = True
    verify_output = True
    remove_args = '--force'


class latest(pull_base):

    def initialize(self):
        self.sub_stuff['ntdi'] = NoTagDockerImages(self)
        super(latest, self).initialize()

    def init_image_fn(self):
        ntdi = self.sub_stuff['ntdi']
        image_fn = ntdi.full_name_from_defaults()
        self.sub_stuff["image_fn"] = image_fn
        return image_fn

    def run_once(self):
        ntdi = self.sub_stuff['ntdi']
        # Remove all images matching image_fn w/o tag
        ntdi.clean_all([self.sub_stuff["image_fn"]])
        super(latest, self).run_once()

    def exitcheck(self):
        # Don't call super-class, it uses regular DockerImages
        ntdi = self.sub_stuff['ntdi']
        image_fn = self.sub_stuff["image_fn"]
        # List will not include tags!
        ntdilist = ntdi.list_imgs_with_full_name(image_fn)
        self.failif(len(ntdilist) < 2,
                    "Fewer than two images matching %s after pull "
                    "following removal of all matching images"
                    % image_fn)
