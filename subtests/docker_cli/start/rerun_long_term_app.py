"""
Test output of docker start command

docker start full_name

1. Create new container with run long term process.
2. Try to start again running container.
3. Check if start command finished with 0
"""

from start import short_term_app
from dockertest.output import OutputGood


class rerun_long_term_app(short_term_app):
    config_section = 'docker_cli/start/rerun_long_term_app'

    def outputgood(self):
        # Raise exception if problems found
        # but ignore expected error message
        cmdresult = self.sub_stuff['dkrcmd'].cmdresult
        OutputGood(cmdresult, ignore_error=True,
                   skip=['error_check'])
