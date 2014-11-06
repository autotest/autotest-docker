r"""
Summary
---------

Test output of docker Pull command

Operational Summary
----------------------

#. Try to download repository from registry
#. if docker_expected_result == PASS: fail when command exitcode != 0
    #. Check if image is in local repository.
    #. Remote image from local repository
#. If docker_expected_result == FAIL: fail when command exitcode == 0

Prerequisites
---------------------------------------------
*  A *remote* registry server
*  Image on remote registry with 'latest' and some other tag
"""

import time
import httplib
from autotest.client.shared import error
from dockertest.subtest import SubSubtest
from dockertest.images import DockerImages, DockerImage
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd
from dockertest import subtest
from dockertest import config


class pull(subtest.SubSubtestCaller):
    config_section = 'docker_cli/pull'


class pull_base(SubSubtest):

    def initialize(self):
        super(pull_base, self).initialize()
        config.none_if_empty(self.config)
        # Private to this instance, outside of __init__

    def run_once(self):
        super(pull_base, self).run_once()
        # 1. Run with no options

        dkrcmd = AsyncDockerCmd(self, 'pull',
                                self.complete_docker_command_line(),
                                self.config['docker_pull_timeout'])
        self.loginfo("Executing background command: %s" % dkrcmd)
        dkrcmd.execute()
        while not dkrcmd.done:
            self.loginfo("Pulling...")
            time.sleep(3)
        self.sub_stuff["cmdresult"] = dkrcmd.wait()

    def complete_docker_command_line(self):
        full_name = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff["img_fn"] = full_name
        return [full_name]

    def outputcheck(self):
        # Raise exception if problems found
        OutputGood(self.sub_stuff['cmdresult'])

    def postprocess(self):
        super(pull_base, self).postprocess()
        self.outputcheck()
        if self.config["docker_expected_result"] == "PASS":
            self.failif(self.sub_stuff['cmdresult'].exit_status != 0,
                        "Non-zero pull exit status: %s"
                        % self.sub_stuff['cmdresult'])

            di = DockerImages(self.parent_subtest)
            image_list = di.list_imgs_with_full_name(self.sub_stuff["img_fn"])
            self.sub_stuff['image_list'] = image_list
            self.failif(self.sub_stuff['image_list'] == [],
                        "Failed to look up image ")

        elif self.config["docker_expected_result"] == "FAIL":
            self.failif(self.sub_stuff['cmdresult'].exit_status == 0,
                        "Zero pull exit status: Command should fail due to"
                        " wrong command arguments.")

    def cleanup(self):
        super(pull_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if (self.config['remove_after_test'] and
                'image_list' in self.sub_stuff):
            for image in self.sub_stuff["image_list"]:
                try:
                    di = DockerImages(self.parent_subtest)
                    di.remove_image_by_image_obj(image)
                    self.loginfo("Successfully removed test image")
                except error.CmdError:
                    self.logwarning("Image not exist.")


def check_registry(registry_addr):
    conn = httplib.HTTPConnection(registry_addr)
    conn.request("GET", "/")
    r1 = conn.getresponse()
    if r1.status != 200:
        response = r1.read()
        if "docker-registry server" not in response:
            raise error.TestNAError("Registry %s is not docker registry."
                                    " Response: %s" % (registry_addr,
                                                       response))
    else:
        raise error.TestNAError("Registry %s is not"
                                " available." % registry_addr)
