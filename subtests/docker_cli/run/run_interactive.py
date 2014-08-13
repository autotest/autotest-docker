"""
Test start command "cat, .." which needs stdin open all time.
"""

import time
import os

from dockertest.dockercmd import AsyncDockerCmd
from dockertest.output import OutputGood
from run import run_base


class run_interactive(run_base):

    def run_once(self):
        self.loginfo("Starting background docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        in_pipe_r, in_pipe_w = os.pipe()
        dkrcmd = AsyncDockerCmd(self, 'run', self.sub_stuff['subargs'],
                                timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True
        dkrcmd.timeout = 10
        # Runs in background
        dkrcmd.execute(in_pipe_r)
        self.sub_stuff['dkrcmd'] = dkrcmd
        wait = self.config['wait_interactive_cmd']
        icmd = self.config['interactive_cmd'] + "\n"
        # Allow noticable time difference for date command,
        # and eat into dkrcmd timeout after receiving signal.
        time.sleep(wait)
        os.write(in_pipe_w, icmd)

        self.loginfo("Waiting up to %d seconds for exit",
                     dkrcmd.timeout)
        # Throw exception if takes > docker_timeout to exit

        self.loginfo("Container running, waiting %d seconds to finish.", wait)
        self.logdebug("interactive cmds %s", icmd)
        time.sleep(wait)
        os.close(in_pipe_w)
        dkrcmd.wait()

    def postprocess(self):
        super(run_interactive, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        cmdresult = self.sub_stuff['dkrcmd']
        OutputGood(cmdresult)
        expected = self.config['exit_status']
        self.failif(cmdresult.exit_status != expected,
                    "Exit status of %s non-zero: %s"
                    % (cmdresult.command,
                       cmdresult))

        str_in_output = self.config["check_i_cmd_out"]
        cmd_stdout = cmdresult.stdout

        self.failif(str_in_output not in cmd_stdout,
                    "Command %s output must contain %s but doesn't."
                    " Detail:%s" %
                    (self.config["interactive_cmd"],
                     str_in_output,
                     cmdresult))
