"""
Test output of docker Pull command

docker commit full_name

1. Try to download repository from registry
2. Check if image is in local repository.
3. Remote image from local repository
"""

from commit import commit_base

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

class good(commit_base):
    config_section = 'docker_cli/commit/good'
