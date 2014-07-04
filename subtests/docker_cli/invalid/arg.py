"""
Test the invalid charactors for docker run

docker run [OPTION] IMAGE [COMMAND] [ARG...]

subtest-arg: the invalid charactor occurs in [ARG...]
  the arg option is invalid
  the arg option is available, but the behind value is invalid
"""

from invalid import invalid_base


class arg(invalid_base):
    config_section = 'docker_cli/invalid/arg'
