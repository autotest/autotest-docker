"""
Test output of docker Pull command

docker pull full_name_wrong_tag

1. Try to download repository from wrong registry
2. Command should fail.
"""
from pull import pull_base
from dockertest.output import OutputNotBad


class wrong_tag(pull_base):

    def outputcheck(self):
        # Only verify no panics or really bad stuff
        OutputNotBad(self.sub_stuff['dkrcmd'].cmdresult)
