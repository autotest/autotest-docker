"""
Test the invalid charactors for docker run

docker run [OPTION] IMAGE

subtest-image:  the invalid charactor occurs in IMAGE
  the image name are not allowed, It contains the charactors
  which are not belong to [a-z-0-9_.]
  the image name are avalibled, but It's not existing in docker repo
"""

from invalid import invalid_base

class image(invalid_base):
    config_section = 'docker_cli/invalid/image'

