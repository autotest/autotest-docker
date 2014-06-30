"""
Test the invalid charactors for docker run

docker run [OPTION]

subtest-option: the invalid charactor occurs in [OPTIONS]
  the invalid charactor occurs in parameter
  (e.g. -b). In fact, '-b' is invalid.
  the invalid charactor occurs in parameter value
  (e.g. -p 10.66.13.175:8000:9900).
  In fact '-p' is available, but behind value is invalid.
"""

from invalid import invalid_base

class option(invalid_base):
    config_section = 'docker_cli/invalid/option'

