"""
Test catching a signal inside a container
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import signal
import time

from autotest.client import utils
from dockertest.dockercmd import AsyncDockerCmd
from run_simple import run_base


class run_signal(run_base):
    config_section = 'docker_cli/run_simple/run_true'

    def run_once(self):
        super(run_base, self).run_once()    # Prints out basic info
        sig = getattr(signal, self.config['listen_signal'])
        dkrcmd = AsyncDockerCmd(self.parentSubtest, 'run',
                                self.subStuff['subargs'])
        # Runs in background
        self.subStuff['cmdresult'] = dkrcmd.execute()
        pid = dkrcmd.process_id
        self.loginfo("Container running, waiting %d seconds to send signal"
                     % self.config['wait_start'])
        # Don't signal until contained-shell is most likely running
        time.sleep(self.config['wait_start'])

        self.loginfo("Signaling pid %d with signal %s",
                     pid, self.config['listen_signal'])
        utils.signal_pid(pid, sig)
        self.loginfo("Waiting up to %d seconds for exit",
                     dkrcmd.timeout)
        # Throw exception if takes > docker_timeout to exit
        dkrcmd.wait()
