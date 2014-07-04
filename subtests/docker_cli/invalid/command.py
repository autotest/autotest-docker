"""
Test the invalid charactors for docker run

docker run [OPTION] IMAGE [COMMAND]

subtest-command:the invalid charactor occurs in [COMMAND]
  the command parameter is invalid.(e.g. -@, -^)
  the command parameter is availble, but the behind value is invalid.
"""

from invalid import invalid_base


class command(invalid_base):
    config_section = 'docker_cli/invalid/command'
