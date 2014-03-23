"""
Test executing /bin/false inside a container returns exit code 1
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from run_simple import run_base


class run_false(run_base):
    config_section = 'docker_cli/run_simple/run_false'
