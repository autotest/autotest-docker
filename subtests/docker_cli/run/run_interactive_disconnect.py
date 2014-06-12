"""
1) Start docker run -d --interactive --name=xxx fedora cat
2) Start docker attach xxx
3) Try write to stdin using docker attach process (should pass)
4) check if docker attach process get input.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import time
import os

from autotest.client import utils
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest.containers import DockerContainers
from dockertest.output import OutputGood
from run import run_base


class run_interactive_disconnect(run_base):

    def initialize(self):
        super(run_interactive_disconnect, self).initialize()
        rand_name = utils.generate_random_string(8)
        self.sub_stuff["rand_name"] = rand_name
        self.sub_stuff["subargs"].insert(0, "--name=\"%s\"" % rand_name)
        self.sub_stuff["cont"] = DockerContainers(self.parent_subtest)

    def run_once(self):
        self.loginfo("Starting background docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        in_pipe_r, in_pipe_w = os.pipe()
        dkrcmd = DockerCmd(self.parent_subtest, 'run',
                           self.sub_stuff['subargs'],
                           timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True
        # Runs in background
        results = self.sub_stuff['cmdresult'] = dkrcmd.execute()
        # Allow noticable time difference for date command,
        # and eat into dkrcmd timeout after receiving signal.
        # Throw exception if takes > docker_timeout to exit
        if results.exit_status != self.config['exit_status']:
            return

        attach_options = self.config['attach_options_csv'].split(',')
        self.sub_stuff['subargs_a'] = attach_options

        c_name = self.sub_stuff["rand_name"]
        cid = self.sub_stuff["cont"].list_containers_with_name(c_name)
        self.sub_stuff["containers"].append(c_name)

        self.failif(cid == [],
                    "Unable to search container with name %s" % (c_name))

        self.sub_stuff['subargs_a'].append(c_name)

        dkrcmd = AsyncDockerCmd(self.parent_subtest, 'attach',
                                self.sub_stuff['subargs_a'],
                                timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmdresult_attach'] = dkrcmd.execute(in_pipe_r)
        os.write(in_pipe_w, self.config['interactive_cmd'] + "\n")
        pid = dkrcmd.process_id
        time.sleep(self.config['wait_interactive_cmd'])
        os.kill(pid, 9)
        try:
            dkrcmd.wait()
        except AssertionError:
            pass

    def postprocess(self):
        super(run_interactive_disconnect, self).postprocess()
        # Fail test if bad command or other stdout/stderr problems detected

        OutputGood(self.sub_stuff['cmdresult'])
        expected = self.config['exit_status']
        self.failif(self.sub_stuff['cmdresult'].exit_status != expected,
                    "Exit status of %s non-zero: %s"
                    % (self.sub_stuff["cmdresult"].command,
                       self.sub_stuff['cmdresult']))

        str_in_output = self.config["check_i_cmd_out"]

        cmd_stdout_attach = self.sub_stuff['cmdresult_attach'].stdout

        self.failif(not str_in_output in cmd_stdout_attach,
                    "Command %s output must contain %s but doesn't."
                    " Detail:%s" %
                   (self.config["bash_cmd"],
                    str_in_output,
                    self.sub_stuff['cmdresult_attach']))

    def cleanup(self):
        c_name = self.sub_stuff["rand_name"]
        try:
            self.sub_stuff["cont"].kill_container_by_name(c_name)
        except KeyError:
            pass  # removal was the goal
        super(run_interactive_disconnect, self).cleanup()
