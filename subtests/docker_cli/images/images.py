"""
Test output of docker Images command

1. Attempt to parse 'docker images' table output
2. Fail if table-format changes or is not parseable
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest import subtest
from dockertest.images import DockerImages
import logging

class images(subtest.Subtest):
    config_section = 'docker_cli/images'

    def initialize(self):
        super(images, self).initialize()

    def run_once(self):
        super(images, self).run_once()
        # 1. Run with no options
        d = DockerImages(self)
        logging.info(d.list_imgs_full_name())
