"""
Test output of docker Images command

1. Attempt to parse 'docker images' table output
2. Fail if table-format changes or is not parseable
"""

from dockertest import subtest
from dockertest.images import DockerImages

class images(subtest.Subtest):
    config_section = 'docker_cli/images'

    def initialize(self):
        super(images, self).initialize()

    def run_once(self):
        super(images, self).run_once()
        # 1. Run with no options
        d = DockerImages(self)
        self.loginfo("Images names: %s", d.list_imgs_full_name())
