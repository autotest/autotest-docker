"""
Test output of docker attach command
"""

import time
import os
from autotest.client import utils
from autotest.client.shared import error
from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers
from dockertest.images import DockerImages
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest import subtest

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


class attach(subtest.SubSubtestCaller):
    config_section = 'docker_cli/attach'


class attach_base(SubSubtest):

    def initialize(self):
        super(attach_base, self).initialize()
        self.sub_stuff['subargs'] = self.config['run_options_csv'].split(',')
        fin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['subargs'].append(fin)
        self.sub_stuff['subargs'] += self.config['bash_cmd'].split(',')
        self.sub_stuff['subargs'].append(self.config['cmd'])
        self.sub_stuff["containers"] = []
        self.sub_stuff["images"] = []
        self.sub_stuff["cont"] = DockerContainers(self.parent_subtest)
        self.sub_stuff["file_desc"] = []

    def cleanup(self):
        super(attach_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['remove_after_test']:
            for cont in self.sub_stuff["containers"]:
                dkrcmd = DockerCmd(self.parent_subtest, "rm",
                                   ['--volumes', '--force', cont])
                cmdresult = dkrcmd.execute()
                msg = (" removed test container: %s" % cont)
                if cmdresult.exit_status == 0:
                    self.logdebug("Successfully" + msg)
                else:
                    self.logwarning("Failed" + msg)
            for image in self.sub_stuff["images"]:
                try:
                    di = DockerImages(self.parent_subtest)
                    self.logdebug("Removing image %s", image)
                    di.remove_image_by_full_name(image)
                    self.logdebug("Successfully removed test image: %s",
                                 image)
                except error.CmdError, e:
                    error_text = "tagged in multiple repositories"
                    if not error_text in e.result_obj.stderr:
                        raise


class simple_base(attach_base):

    def initialize(self):
        super(simple_base, self).initialize()
        rand_name = utils.generate_random_string(8)
        self.sub_stuff["rand_name"] = rand_name
        self.sub_stuff["subargs"].insert(0, "--name=\"%s\"" % rand_name)

        run_in_pipe_r, run_in_pipe_w = os.pipe()
        self.sub_stuff['file_desc'].append(run_in_pipe_r)
        self.sub_stuff['file_desc'].append(run_in_pipe_w)
        self.sub_stuff["run_in_pipe_w"] = run_in_pipe_w
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
        self.sub_stuff["containers"].append(c_name)
        cid = self.sub_stuff["cont"].list_containers_with_name(c_name)

        self.failif(cid == [],
                    "Unable to search container with name %s" % (c_name))


    def run_once(self):
        super(simple_base, self).run_once()
        self.loginfo("Starting background docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        attach_in_pipe_r, attach_in_pipe_w = os.pipe()
        self.sub_stuff['file_desc'].append(attach_in_pipe_r)
        self.sub_stuff['file_desc'].append(attach_in_pipe_w)

        self.sub_stuff['subargs_a'].append(self.sub_stuff["rand_name"])

        dkrcmd = AsyncDockerCmd(self.parent_subtest, 'attach',
                                self.sub_stuff['subargs_a'],
                                timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmd_attach'] = dkrcmd
        self.sub_stuff['cmdresult_attach'] = dkrcmd.execute(attach_in_pipe_r)


        time.sleep(self.config['wait_interactive_cmd'])
        # This input should be ignored.
        os.write(self.sub_stuff["run_in_pipe_w"],
                 self.config['interactive_cmd_run'] + "\n")

        # This input should be passed to container.
        os.write(attach_in_pipe_w,
                 self.config['interactive_cmd_attach'] + "\n")

        time.sleep(self.config['wait_interactive_cmd'])

    def postprocess(self):
        super(attach_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected

        OutputGood(self.sub_stuff['cmdresult'])

        str_run_cmd_output = self.config["check_run_cmd_out"]
        str_attach_cmd_output = self.config["check_attach_cmd_out"]
        cmd_stdout = self.sub_stuff['cmd_run'].stdout
        cmd_stdout_attach = self.sub_stuff['cmd_attach'].stdout

        self.failif(str_run_cmd_output not in cmd_stdout,
                    "Command %s output must contain %s but doesn't."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_run_cmd_output,
                         self.sub_stuff['cmdresult']))

        self.failif(str_attach_cmd_output not in cmd_stdout,
                    "Command %s output must contain %s but doesn't."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_attach_cmd_output,
                         self.sub_stuff['cmdresult']))

        self.failif(str_run_cmd_output not in cmd_stdout_attach,
                    "Command %s output must contain %s but doesn't."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_run_cmd_output,
                         self.sub_stuff['cmdresult_attach']))

        self.failif(str_attach_cmd_output not in cmd_stdout_attach,
                    "Command %s output must contain %s but doesn't."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_attach_cmd_output,
                         self.sub_stuff['cmdresult_attach']))

    def cleanup(self):
        super(simple_base, self).cleanup()
        for fd in self.sub_stuff["file_desc"]:
            os.close(fd)


class sig_proxy_off_base(simple_base):

    def run_once(self):
        super(simple_base, self).run_once()
        self.loginfo("Starting background docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        self.sub_stuff['subargs_a'].append(self.sub_stuff["rand_name"])

        dkrcmd = AsyncDockerCmd(self.parent_subtest, 'attach',
                                self.sub_stuff['subargs_a'],
                                timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmd_attach'] = dkrcmd
        self.sub_stuff['cmdresult_attach'] = dkrcmd.execute()

        time.sleep(self.config['wait_interactive_cmd'])
        # This input should be ignored.
        pid = dkrcmd.process_id
        os.kill(pid, int(self.config["signal"]))

        # This input should be passed to container.

        time.sleep(self.config['wait_interactive_cmd'])

    def postprocess(self):
        super(attach_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected

        OutputGood(self.sub_stuff['cmdresult'])

        c_name = self.sub_stuff["rand_name"]
        containers = self.sub_stuff['cont'].list_containers_with_name(c_name)
        if containers:
            self.failif("Exited" in containers[0].status,
                        "Docker command was killed by attached docker when"
                        "sig-proxy=false. It shouldn't happened.")
        else:
            self.logerror("Unable to find started container.")
