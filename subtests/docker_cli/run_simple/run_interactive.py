"""
Test start command "cat, .." which needs stdin open all time.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import signal
import time
import os

from autotest.client import utils
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.output import OutputGood
from run_simple import run_base


class run_interactive(run_base):

    def run_once(self):
        self.loginfo("Starting background docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        in_pipe_r, in_pipe_w = os.pipe()
        dkrcmd = AsyncDockerCmd(self.parent_subtest, 'run',
                                self.sub_stuff['subargs'],
                                timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True
        dkrcmd.timeout = 10
        # Runs in background
        self.sub_stuff['cmdresult'] = dkrcmd.execute(in_pipe_r)
        # Allow noticable time difference for date command,
        # and eat into dkrcmd timeout after receiving signal.
        time.sleep(self.config['wait_interactive_cmd'])
        os.write(in_pipe_w, self.config['interactive_cmd'] + "\n")

        self.loginfo("Waiting up to %d seconds for exit",
                     dkrcmd.timeout)
        # Throw exception if takes > docker_timeout to exit

        self.loginfo("Container running, waiting %d seconds to finish"
                     "interactive cmds %s" %
                                     (self.config['wait_interactive_cmd'],
                                      self.config['interactive_cmd']))
        time.sleep(self.config['wait_interactive_cmd'])
        os.close(in_pipe_w)
        dkrcmd.wait()


    def postprocess(self):
        super(run_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        OutputGood(self.sub_stuff['cmdresult'])
        expected = self.config['exit_status']
        self.failif(self.sub_stuff['cmdresult'].exit_status != expected,
                    "Exit status of %s non-zero: %s"
                    % (self.sub_stuff["cmdresult"].command,
                       self.sub_stuff['cmdresult']))

        str_in_output = self.config["check_i_cmd_out"]
        cmd_stdout = self.sub_stuff['cmdresult'].stdout

        self.failif(not str_in_output in cmd_stdout,
                    "Command %s output must contain %s but doesn't."
                    " Detail:%s" %
                        (self.config["interactive_cmd"],
                         str_in_output,
                         self.sub_stuff['cmdresult']))
