"""
Test the invalid charactors for docker run

docker run [OPTION] IMAGE [COMMAND] [ARG...]

subtest-arg: the invalid charactor occurs in [ARG...]
  the arg option is invalid
  the arg option is available, but the behind value is invalid
"""

from invalid import invalid_base

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


class arg(invalid_base):
    config_section = 'docker_cli/invalid/arg'

