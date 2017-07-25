"""
Test output of docker Pull command

docker pull wrong_full_name

1. Try to download repository from wrong registry
2. Command should fail.
"""

from pull import pull_base
from dockertest.output import OutputNotBad


class wrong_registry_addr(pull_base):

    @staticmethod
    def check_registry(registry_addr):
        # registry_addr is expected to be incorrect
        del registry_addr

    def outputcheck(self):
        # Only verify no panics or really bad stuff
        OutputNotBad(self.sub_stuff['dkrcmd'].cmdresult)
