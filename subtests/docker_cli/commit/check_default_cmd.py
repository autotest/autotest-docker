"""
Test output of docker Pull command

docker commit full_name

1. Try to download repository from registry
2. Check if image is in local repository.
3. Pass to image default command.
4. Try to start default command.
5. Check results of default command.
6. Kill container started with default command.
3. Remote image from local repository
"""

from commit import commit_base
from dockertest.output import OutputGood
from dockertest.dockercmd import DockerCmd
from dockertest.containers import DockerContainers

class check_default_cmd(commit_base):
    config_section = 'docker_cli/commit/check_default_cmd'

    def postprocess(self):
        self.loginfo("postprocess()")
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
        # Check if is possible start image with default command.
        dc = DockerCmd(self.parent_subtest, "run",
                       [self.sub_stuff['image_list'][0].long_id],
                       timeout=self.config['docker_timeout'])
        results = dc.execute()

        dct = DockerContainers(self.parent_subtest)
        cnts = dct.list_containers()
        for cont in cnts:
            if cont.image_name == self.sub_stuff['image_list'][0].full_name:
                try:
                    dct.kill_container_by_long_id(cont.long_id)
                except ValueError:
                    pass
                dc = DockerCmd(self.parent_subtest, "rm", ["-f", cont.long_id])
                rm_results = dc.execute()
                self.failif(rm_results.exit_status != 0,
                    "Non-zero commit exit status: %s"
                    % rm_results)

        self.failif(results.exit_status != 0,
                    "Non-zero commit exit status: %s"
                    % results)

        self.failif(not self.config['check_results_contain'] in results.stdout,
                    "Unable to start image with default command: %s"
                    % results)
