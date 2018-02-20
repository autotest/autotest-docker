"""
Summary
---------

Test functioning of docker attach command

Operational Summary
----------------------

#. Run container w/ control over stdin & stdout
#. Separately attach to the container in another process
#. Send input to container via stdin, monitor attach process stdout
#. Verify output matches input
"""

import time
import os
from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers
from dockertest.images import DockerImages
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd
from dockertest import subtest


class attach(subtest.SubSubtestCaller):
    config_section = 'docker_cli/attach'


class attach_base(SubSubtest):

    def wait_interactive_cmd(self):
        wait = self.config['wait_interactive_cmd']
        self.loginfo("Waiting %s seconds for the fog to settle."
                     % wait)
        time.sleep(wait)

    def image_exist(self, image_name):
        di = DockerImages(self)
        image_list = di.get_dockerimages_list()
        exist_status = DockerImages.filter_list_full_name(image_list,
                                                          image_name)
        return exist_status

    def pull_image(self, image_name):
        dkrcmd = AsyncDockerCmd(self, 'pull', [image_name],
                                self.config['docker_timeout'])
        self.loginfo("Executing background command: %s" % dkrcmd)
        dkrcmd.execute()
        while not dkrcmd.done:
            self.loginfo("Pulling...")
            time.sleep(3)
        self.failif_ne(dkrcmd.exit_status, 0,
                       "Fail to download image %s"
                       % image_name)

    def initialize(self):
        super(attach_base, self).initialize()
        self.sub_stuff['subargs'] = self.config['run_options_csv'].split(',')
        fin = DockerImage.full_name_from_defaults(self.config)
        if self.image_exist(fin) == []:
            self.pull_image(fin)
        self.sub_stuff['subargs'].append(fin)
        self.sub_stuff['subargs'] += ['bash', '-c', self.config['cmd']]
        self.sub_stuff["containers"] = []
        self.sub_stuff["images"] = []
        self.sub_stuff["cont"] = DockerContainers(self)
        self.sub_stuff["file_desc"] = []

    def cleanup(self):
        super(attach_base, self).cleanup()
        if self.config['remove_after_test']:
            dc = self.sub_stuff["cont"]
            di = di = DockerImages(self)
            dc.clean_all(self.sub_stuff["containers"])
            di.clean_all(self.sub_stuff["images"])


class simple_base(attach_base):

    def initialize(self):
        super(simple_base, self).initialize()
        rand_name = self.sub_stuff['cont'].get_unique_name()
        self.sub_stuff["rand_name"] = rand_name
        self.sub_stuff["subargs"].insert(0, "--name=\"%s\"" % rand_name)

        run_in_pipe_r, run_in_pipe_w = os.pipe()
        self.sub_stuff['file_desc'].append(run_in_pipe_r)
        self.sub_stuff['file_desc'].append(run_in_pipe_w)
        self.sub_stuff["run_in_pipe_w"] = run_in_pipe_w
        dkrcmd = AsyncDockerCmd(self, 'run', self.sub_stuff['subargs'])

        # Runs in background
        self.sub_stuff['cmdresult'] = dkrcmd.execute(run_in_pipe_r)
        self.sub_stuff['cmd_run'] = dkrcmd
        dkrcmd.wait_for_ready()
        self.logdebug("Detail after waiting: %s", dkrcmd.cmdresult)

        attach_options = self.config['attach_options_csv'].split(',')
        self.sub_stuff['subargs_a'] = attach_options

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

        dkrcmd = AsyncDockerCmd(self, 'attach', self.sub_stuff['subargs_a'])
        # Runs in background
        self.sub_stuff['cmd_attach'] = dkrcmd
        self.sub_stuff['cmdresult_attach'] = dkrcmd.execute(attach_in_pipe_r)
        self.wait_interactive_cmd()
        self.logdebug("Before input should be ignored: %s", dkrcmd.cmdresult)

        # This input should be ignored.
        send_str = self.config['interactive_cmd_run']
        self.logdebug("About to send '%s' to run_in_pipe" % send_str)
        os.write(self.sub_stuff["run_in_pipe_w"], send_str + "\n")

        self.logdebug("Before input should be passed: %s", dkrcmd.cmdresult)
        # This input should be passed to container.
        send_str = self.config['interactive_cmd_attach']
        self.logdebug("About to send '%s' to attach_in_pipe" % send_str)
        os.write(attach_in_pipe_w, send_str + "\n")

        self.wait_interactive_cmd()
        self.logdebug("After input was passed: %s", dkrcmd.cmdresult)

    def failif_contain(self, check_for, in_output, details):
        self.failif(check_for in in_output,
                    "Command '%s' output must not contain '%s' but does."
                    " Detail: %s" % (self.config["cmd"],
                                     check_for, details))
        self.logdebug("Output does NOT contain '%s'", check_for)

    def failif_not_contain(self, check_for, in_output, details):
        self.failif_not_in(check_for, in_output,
                           "Output from '%s' command. Details: %s" %
                           (self.config["cmd"], details))
        self.logdebug("Output does contain '%s'", check_for)

    def verify_output(self):
        # e.g. "run_data"
        check_for = self.config["check_run_cmd_out"]
        in_output = self.sub_stuff['cmd_run'].stdout
        details = self.sub_stuff['cmdresult']
        self.failif_not_contain(check_for, in_output, details)

        # e.g. "append_data"
        check_for = self.config["check_attach_cmd_out"]
        self.failif_not_contain(check_for, in_output, details)

        in_output = self.sub_stuff['cmd_attach'].stdout
        details = self.sub_stuff['cmdresult_attach']
        self.failif_not_contain(check_for, in_output, details)

        in_output = self.sub_stuff['cmd_attach'].stdout
        self.failif_not_contain(check_for, in_output, details)

    def postprocess(self):
        super(simple_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        OutputGood(self.sub_stuff['cmdresult'])
        self.verify_output()

    def cleanup(self):
        for fd in self.sub_stuff["file_desc"]:
            os.close(fd)
        super(simple_base, self).cleanup()


class sig_proxy_off_base(attach_base):

    def initialize(self):
        super(sig_proxy_off_base, self).initialize()
        rand_name = self.sub_stuff['cont'].get_unique_name()

        self.sub_stuff["rand_name"] = rand_name
        self.sub_stuff["subargs"].insert(0, "--name=\"%s\"" % rand_name)

        run_in_pipe_r, run_in_pipe_w = os.pipe()
        self.sub_stuff['file_desc'].append(run_in_pipe_r)
        self.sub_stuff['file_desc'].append(run_in_pipe_w)
        self.sub_stuff["run_in_pipe_w"] = run_in_pipe_w
        dkrcmd = AsyncDockerCmd(self, 'run', self.sub_stuff['subargs'])

        # Runs in background
        self.sub_stuff['cmdresult'] = dkrcmd.execute(run_in_pipe_r)
        self.sub_stuff['cmd_run'] = dkrcmd

        attach_options = self.config['attach_options_csv'].split(',')
        self.sub_stuff['subargs_a'] = attach_options

        dkrcmd.wait_for_ready()
        c_name = self.sub_stuff["rand_name"]
        self.sub_stuff["containers"].append(c_name)
        cid = self.sub_stuff["cont"].list_containers_with_name(c_name)

        self.failif(cid == [],
                    "Unable to search container with name %s, detail: %s"
                    % (c_name, dkrcmd))

    def run_once(self):
        super(sig_proxy_off_base, self).run_once()
        self.loginfo("Starting background docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        self.sub_stuff['subargs_a'].append(self.sub_stuff["rand_name"])

        dkrcmd = AsyncDockerCmd(self, 'attach', self.sub_stuff['subargs_a'])
        # Runs in background
        self.sub_stuff['cmd_attach'] = dkrcmd
        self.sub_stuff['cmdresult_attach'] = dkrcmd.execute()

        self.wait_interactive_cmd()

        pid = dkrcmd.process_id
        os.kill(pid, int(self.config["signal"]))

        self.wait_interactive_cmd()
        self.logdebug("After the killing: %s", dkrcmd.cmdresult)

    def check_containers(self, containers):
        if containers:
            self.failif("Exited" in containers[0].status,
                        "Docker command was killed by attached docker"
                        " despite --sig-proxy=false.")
        else:
            self.logerror("Unable to find started container.")

    def postprocess(self):
        super(sig_proxy_off_base, self).postprocess()

        OutputGood(self.sub_stuff['cmdresult'])

        c_name = self.sub_stuff["rand_name"]
        containers = self.sub_stuff['cont'].list_containers_with_name(c_name)
        self.check_containers(containers)

    def cleanup(self):
        for fd in self.sub_stuff["file_desc"]:
            os.close(fd)
        super(sig_proxy_off_base, self).cleanup()
