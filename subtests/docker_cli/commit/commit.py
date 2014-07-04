"""
Test output of docker Commit command

Initialize
1. Make new image name.
2. Make changes in image by docker run [dockerand_data_prepare_cmd].
run_once
3. commit changes.
postprocess
4. check if committed image exists.
5. check if values in changed files for image are correct.
clean
6. remote committed image from local repo.
"""

import time
from autotest.client import utils
from autotest.client.shared import error
from dockertest.subtest import SubSubtest
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
        di = DockerImages(self.parent_subtest)
        return di.list_imgs_with_full_name(full_name)

    def initialize(self):
        super(commit_base, self).initialize()
        config.none_if_empty(self.config)
        di = DockerImages(self.parent_subtest)
        name_prefix = self.config["commit_repo_name_prefix"]
        new_img_name = di.get_unique_name(name_prefix)
        self.sub_stuff["new_image_name"] = new_img_name

        self.sub_stuff['rand_data'] = utils.generate_random_string(8)
        cmd_with_rand = (self.config['docker_data_prepare_cmd']
                         % self.sub_stuff['rand_data'])

        fqin = DockerImage.full_name_from_defaults(self.config)
        prep_changes = DockerCmd(self.parent_subtest, "run",
                                 ["--detach",
                                  fqin,
                                  cmd_with_rand],
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
        run_params = self.config["commit_run_params"]
        repo_addr = self.sub_stuff["new_image_name"]

        cmd = []
        if c_author:
            cmd.append("-a %s" % c_author)
        if c_msg:
            cmd.append("-m %s" % c_msg)
        if run_params:
            cmd.append("--run=%s" % run_params)

        cmd.append(self.sub_stuff["container"])
        cmd.append(repo_addr)
        self.sub_stuff["commit_cmd"] = cmd
        return cmd

    def run_once(self):
        super(commit_base, self).run_once()
        dkrcmd = AsyncDockerCmd(self.parent_subtest, 'commit',
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
        if self.config["docker_expected_result"] == "PASS":
            # Raise exception if problems found
            OutputGood(self.sub_stuff['cmdresult'])
            self.failif(self.sub_stuff['cmdresult'].exit_status != 0,
                        "Non-zero commit exit status: %s"
                        % self.sub_stuff['cmdresult'])

            im = self.check_image_exists(self.sub_stuff["new_image_name"])
            # Needed for cleanup
            self.sub_stuff['image_list'] = im
            self.failif(len(im) < 1,
                        "Failed to look up committed image ")
            self.check_file_in_image()

        elif self.config["docker_expected_result"] == "FAIL":
            og = OutputGood(self.sub_stuff['cmdresult'], ignore_error=True)
            es = self.sub_stuff['cmdresult'].exit_status == 0
            self.failif(not og or not es,
                        "Zero commit exit status: Command should fail due to"
                        " wrong command arguments.")

    def cleanup(self):
        super(commit_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if (self.config['remove_after_test'] and
           'image_list' in self.sub_stuff):
            dkrcmd = DockerCmd(self.parent_subtest, "rm",
                               ['--volumes', '--force',
                                self.sub_stuff["container"]])
            cmdresult = dkrcmd.execute()
            msg = (" removed test container: %s" % self.sub_stuff["container"])
            if cmdresult.exit_status == 0:
                self.loginfo("Successfully" + msg)
            else:
                self.logwarning("Failed" + msg)
            for image in self.sub_stuff["image_list"]:
                try:
                    di = DockerImages(self.parent_subtest)
                    self.logdebug("Removing image %s", image.full_name)
                    di.remove_image_by_image_obj(image)
                    self.loginfo("Successfully removed test image: %s",
                                 image.full_name)
                except error.CmdError, e:
                    error_text = "tagged in multiple repositories"
                    if not error_text in e.result_obj.stderr:
                        raise

    def check_file_in_image(self):
        commit_changed_files = self.config["commit_changed_files"]
        repo_addr = self.sub_stuff["new_image_name"]
        for f_name in commit_changed_files.split(";"):
            f_read_cmd = self.config['docker_read_file_cmd'] % f_name

            cm = DockerCmd(self.parent_subtest, "run",
                           ["--rm", repo_addr, f_read_cmd],
                           self.config['docker_commit_timeout'])
            results = cm.execute()
            if results.exit_status == 0:
                self.failif((results.stdout.strip() !=
                             self.sub_stuff["rand_data"]),
                            "Data read from image do not match"
                            " data written to container during"
                            " test initialization: %s != %s" %
                            (results.stdout.strip(),
                             self.sub_stuff["rand_data"]))
