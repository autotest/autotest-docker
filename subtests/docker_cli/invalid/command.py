"""
Test the invalid charactors for docker run

docker run [OPTION] IMAGE [COMMAND]

subtest-command:the invalid charactor occurs in [COMMAND]
  the command parameter is invalid.(e.g. -@, -^)
  the command parameter is availble, but the behind value is invalid.
"""

from invalid import invalid_base

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


class command(invalid_base):
    config_section = 'docker_cli/invalid/command'

