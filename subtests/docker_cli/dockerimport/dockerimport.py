"""
Based on config['test_subsection_postfixes'] load module, call function.
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest.subtest import SubSubtestCaller

class dockerimport(SubSubtestCaller):
    config_section = 'docker_cli/dockerimport'
