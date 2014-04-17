"""
Test run

1) Start docker run --interactive --attach=stdout --name=xxx fedora cat
2) Start docker attach xxx
3) Try write to stdin using docker run process (shouldn't pass)
4) Try write to stdin using docker attach process (should pass)
5) check if docker run process get input from attach process.
6) check if docker attach/run process don't get stdin from docker run process.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import signal
import time
import os

from autotest.client import utils
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest.containers import DockerContainers
from dockertest.output import OutputGood
from run_simple import run_base


class run_attach_stdout(run_base):

    def initialize(self):
        super(run_attach_stdout, self).initialize()
        rand_name = utils.generate_random_string(8)
        self.sub_stuff["rand_name"] = rand_name
        self.sub_stuff["subargs"].insert(0, "--name=\"%s\"" % rand_name)
        self.sub_stuff["cont"] = DockerContainers(self.parent_subtest)

    def run_once(self):
        self.loginfo("Starting background docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        run_in_pipe_r, run_in_pipe_w = os.pipe()
        attach_in_pipe_r, attach_in_pipe_w = os.pipe()
        dkrcmd = AsyncDockerCmd(self.parent_subtest, 'run',
                           self.sub_stuff['subargs'],
                           timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmdresult'] = dkrcmd.execute(run_in_pipe_r)
        self.sub_stuff['cmd_run'] = dkrcmd
        # Allow noticable time difference for date command,
        # and eat into dkrcmd timeout after receiving signal.
        # Throw exception if takes > docker_timeout to exit

        attach_options = self.config['attach_options_csv'].split(',')
        self.sub_stuff['subargs_a'] = attach_options

        time.sleep(self.config['wait_interactive_cmd'])
        c_name = self.sub_stuff["rand_name"]
        cid = self.sub_stuff["cont"].list_containers_with_name(c_name)

        self.failif(cid == [],
                    "Unable to search container with name %s" % (c_name))

        self.sub_stuff['subargs_a'].append(c_name)

        dkrcmd = AsyncDockerCmd(self.parent_subtest, 'attach',
                                self.sub_stuff['subargs_a'],
                                timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmd_attach'] = dkrcmd
        self.sub_stuff['cmdresult_attach'] = dkrcmd.execute(attach_in_pipe_r)


        # This input should be ignored.
        os.write(run_in_pipe_w,
                 self.config['interactive_cmd_run'] + "\n")

        # This input should be passed to container.
        os.write(attach_in_pipe_w,
                 self.config['interactive_cmd_attach'] + "\n")

        time.sleep(self.config['wait_interactive_cmd'])

    def postprocess(self):
        super(run_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected

        OutputGood(self.sub_stuff['cmdresult'])

        str_in_output = self.config["check_i_cmd_out"]
        str_not_in_output = self.config["check_not_i_cmd_out"]
        cmd_stdout = self.sub_stuff['cmd_run'].stdout
        cmd_stdout_attach = self.sub_stuff['cmd_attach'].stdout

        self.failif(str_not_in_output in cmd_stdout,
                    "Command %s output must not contain %s."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_not_in_output,
                         self.sub_stuff['cmdresult']))

        self.failif(str_not_in_output in cmd_stdout_attach,
                    "Command %s output must not contain %s."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_not_in_output,
                         self.sub_stuff['cmdresult_attach']))

        self.failif(not str_in_output in cmd_stdout_attach,
                    "Command %s output must contain %s but doesn't."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_in_output,
                         self.sub_stuff['cmdresult_attach']))

    def cleanup(self):
        super(run_attach_stdout, self).cleanup()
        c_name = self.sub_stuff["rand_name"]
        self.sub_stuff["cont"].kill_container_by_name(c_name)
