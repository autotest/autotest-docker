r"""
Summary
---------

Test to confirm output table-format of docker CLI
'images' command.

Operational Summary
----------------------

#. Attempt to parse 'docker images' table output
#. Fail if table-format changes or is not parseable

Prerequisites
---------------

Configuration
---------------
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
