"""
Test run

1) Start docker run --interactive --attach=stdout --name=xxx fedora cat
2) Start docker attach xxx
3) Try write to stdin using docker run process (shouldn't pass)
4) Try write to stdin using docker attach process (should pass)
5) check if docker run process get input from attach process.
6) check if docker attach/run process don't get stdin from docker run process.
"""

import time
import os

from autotest.client import utils
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.containers import DockerContainers
from dockertest.output import OutputGood
from run import run_base


class run_attach_stdout(run_base):

    def initialize(self):
        super(run_attach_stdout, self).initialize()
        dc = DockerContainers(self.parent_subtest)
        self.sub_stuff["rand_name"] = rand_name = dc.get_unique_name()
        self.sub_stuff["rand_data"] = utils.generate_random_string(8)
        self.sub_stuff["subargs"].insert(0, "--name=\"%s\"" % rand_name)
        attach_options = self.config['attach_options_csv'].split(',')
        attach_options.append(rand_name)
        self.sub_stuff['attach_options'] = attach_options
        self.sub_stuff["rpipe"], self.sub_stuff["wpipe"] = os.pipe()

    def run_once(self):
        self.logdebug("Starting background docker commands")

        runcmd = AsyncDockerCmd(self.parent_subtest, 'run',
                                self.sub_stuff['subargs'],
                                timeout=self.config['docker_timeout'])
        self.logdebug("Run Command: %s", runcmd.command)

        runcmd.execute(self.sub_stuff["rpipe"])
        ss = self.config['secret_sauce']
        while True:
            stdout = runcmd.stdout
            if stdout.count(ss) >= 1:
                break
            time.sleep(0.1)
        self.loginfo("Container running, waiting for %s seconds.",
                     self.config['wait_interactive_cmd'])
        time.sleep(self.config['wait_interactive_cmd'])
        # Not needed by this process anymore
        os.close(self.sub_stuff["rpipe"])

        self.logdebug("Starting attach command")
        attachcmd = AsyncDockerCmd(self.parent_subtest, 'attach',
                                   self.sub_stuff['attach_options'],
                                   timeout=self.config['docker_timeout'])
        self.logdebug("Attach Command: %s", runcmd.command)
        attachcmd.execute()
        self.loginfo("Waiting for %s seconds for attach",
                     self.config['wait_interactive_cmd'])
        time.sleep(self.config['wait_interactive_cmd'])

        rand_data = self.sub_stuff["rand_data"]
        self.logdebug("Sending test data: %s", rand_data)
        os.write(self.sub_stuff["wpipe"], rand_data)  # line buffered
        #  send EOF to container
        os.close(self.sub_stuff["wpipe"])
        self.logdebug("Waiting for processes to exit")
        self.sub_stuff['run_cmdresult'] = runcmd.wait()
        self.sub_stuff['cmdresult'] = attachcmd.wait()

    def postprocess(self):
        super(run_attach_stdout, self).postprocess()  # checks cmdresult
        cmdresult = self.sub_stuff['cmdresult']
        run_cmdresult = self.sub_stuff['run_cmdresult']
        OutputGood(run_cmdresult)
        rand_data = self.sub_stuff["rand_data"]
        self.failif(cmdresult.stdout.strip().count(rand_data) < 1,
                    "Test data not found on attach command stdout: %s"
                    % cmdresult)

    def cleanup(self):
        super(run_attach_stdout, self).cleanup()
        dc = DockerContainers(self.parent_subtest)
        name = self.sub_stuff["rand_name"]
        try:
            dc.kill_container_by_name(name)
        except ValueError:
            pass  # death was the goal
        dc.remove_by_name(self.sub_stuff["rand_name"])
