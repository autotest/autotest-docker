r"""
Summary
---------

Several variations of running the commit command

Operational Summary
--------------------

#. Make new image name.
#. Make changes in image by docker run.
#. commit changes.
#. check if committed image exists.
#. check if values in changed files for image are correct.
#. remove committed image from local repo.
"""

import time
from autotest.client import utils
from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers
from dockertest.images import DockerImages
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest import subtest
from dockertest import config
from dockertest import xceptions


class commit(subtest.SubSubtestCaller):
    config_section = 'docker_cli/commit'


class commit_base(SubSubtest):

    def check_image_exists(self, full_name):
        di = DockerImages(self)
        return di.list_imgs_with_full_name(full_name)

    def initialize(self):
        super(commit_base, self).initialize()
        config.none_if_empty(self.config)
        di = DockerImages(self)
        new_img_name = di.get_unique_name()
        self.sub_stuff["new_image_name"] = new_img_name

        self.sub_stuff['rand_data'] = utils.generate_random_string(8)
        cmd_with_rand = (self.config['docker_data_prepare_cmd']
                         % self.sub_stuff['rand_data'])

        fqin = DockerImage.full_name_from_defaults(self.config)
        prep_changes = DockerCmd(self, "run",
                                 ["--detach", fqin, cmd_with_rand],
                                 self.config['docker_commit_timeout'])

        results = prep_changes.execute()
        if results.exit_status:
            raise xceptions.DockerTestNAError("Problems during "
                                              "initialization of"
                                              " test: %s", results)
        else:
            self.sub_stuff["container"] = results.stdout.strip()

    def complete_docker_command_line(self):
        c_author = self.config["commit_author"]
        c_msg = self.config["commit_message"]
        repo_addr = self.sub_stuff["new_image_name"]

        cmd = []
        if c_author:
            cmd.append("-a %s" % c_author)
        if c_msg:
            cmd.append("-m %s" % c_msg)

        cmd.append(self.sub_stuff["container"])
        cmd.append(repo_addr)
        self.sub_stuff["commit_cmd"] = cmd
        return cmd

    def run_once(self):
        super(commit_base, self).run_once()
        dkrcmd = AsyncDockerCmd(self, 'commit',
                                self.complete_docker_command_line(),
                                self.config['docker_commit_timeout'])
        self.loginfo("Executing background command: %s" % dkrcmd)
        dkrcmd.execute()
        while not dkrcmd.done:
            self.loginfo("Committing...")
            time.sleep(3)
        self.sub_stuff["cmdresult"] = dkrcmd.wait()

    def postprocess(self):
        super(commit_base, self).postprocess()
        # Raise exception if problems found
        expect = self.config["docker_expected_exit_status"]
        OutputGood(self.sub_stuff['cmdresult'], ignore_error=(expect != 0))

        self.failif_ne(self.sub_stuff['cmdresult'].exit_status, expect,
                       "Command exit status")

        if expect == 0:
            im = self.check_image_exists(self.sub_stuff["new_image_name"])
            # Needed for cleanup
            self.sub_stuff['image_list'] = im
            self.failif(len(im) < 1,
                        "Failed to look up committed image ")
            self.check_file_in_image()

    def cleanup(self):
        super(commit_base, self).cleanup()
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            container = self.sub_stuff.get("container")
            if container:
                dc.clean_all([container])
            di = di = DockerImages(self)
            images = [img.full_name
                      for img in self.sub_stuff.get("image_list", [])]
            di.clean_all(images)

    def check_file_in_image(self):
        commit_changed_files = self.config["commit_changed_files"]
        repo_addr = self.sub_stuff["new_image_name"]
        for f_name in commit_changed_files.split(";"):
            f_read_cmd = self.config['docker_read_file_cmd'] % f_name

            cm = DockerCmd(self, "run", ["--rm", repo_addr, f_read_cmd],
                           self.config['docker_commit_timeout'])
            results = cm.execute()
            if results.exit_status == 0:
                self.failif_ne(results.stdout.strip(),
                               self.sub_stuff["rand_data"],
                               "Data read from image do not match"
                               " data written to container during"
                               " test initialization: %s != %s" %
                               (results.stdout.strip(),
                                self.sub_stuff["rand_data"]))


class good(commit_base):
    pass
