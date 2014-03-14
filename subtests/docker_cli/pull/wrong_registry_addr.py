"""
Test output of docker Pull command

docker pull wrong_full_name

1. Try to download repository from wrong registry
2. Command should fail.
"""

from pull import pull_base

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

class wrong_registry_addr(pull_base):
    config_section = 'docker_cli/pull/wrong_registry_addr'
