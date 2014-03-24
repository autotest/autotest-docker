"""
Test output of docker Pull command

docker pull wrong_full_name

1. Try to download repository from wrong registry
2. Command should fail.
"""

from dockertest import output
from pull import pull_base

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

class wrong_registry_addr(pull_base):
    config_section = 'docker_cli/pull/wrong_registry_addr'

    def outputcheck(self):
        outputgood = output.OutputGood(self.sub_stuff['cmdresult'],
                                       ignore_error=True)
        # This is SUPPOSE to fail, fail test if it succeeds!
        self.failif(outputgood, str(outputgood))
