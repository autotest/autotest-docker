"""
Test catching a sgnal inside a container
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import time, signal
from autotest.client import utils
from dockertest import subtest, images
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.output import OutputGood

class run_signal(subtest.Subtest):
    config_section = 'docker_cli/run_signal'

    def initialize(self):
        super(run_signal, self).initialize()
        self.stuff['subargs'] = self.config['run_options_csv'].split(',')
        fin = images.DockerImage.full_name_from_defaults(self.config)
        self.stuff['subargs'].append(fin)
        self.stuff['subargs'].append('/bin/bash')
        self.stuff['subargs'].append('-c')
        # Write to a file when signal received
        # Loop forever until marker-file exists
        command = ("\"trap '/usr/bin/date > stop' %s; "
                   "while ! [ -f stop ]; do :; done\""
                   % self.config['listen_signal'])
        self.stuff['subargs'].append(command)

    def run_once(self):
        super(run_signal, self).run_once() # Prints out basic info
        sig = getattr(signal, self.config['listen_signal'])
        dkrcmd = AsyncDockerCmd(self, 'run', self.stuff['subargs'])
        # Runs in background
        self.stuff['cmdresult'] = dkrcmd.execute()
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

    def postprocess(self):
        super(run_signal, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        OutputGood(self.stuff['cmdresult'])
        expected = self.config['exit_status']
        actual = self.stuff['cmdresult'].exit_status
        self.failif(actual != expected,
                    "Exit status was %d, not %d. %s" % (actual, expected,
                                                   self.stuff['cmdresult']))
