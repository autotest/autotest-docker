"""
Test output of docker start command

docker start full_name

1. Create new container with run long term process.
2. Kill running container.
2. Wait till end of container command.
3. Try to start container.
4. Check if container still run.
5. Kill container.
"""

from autotest.client.shared import error
from start import short_term_app, DockerContainersCLIRunOnly
from dockertest.dockercmd import DockerCmd

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


class long_term_app(short_term_app):
    config_section = 'docker_cli/start/long_term_app'

    def initialize(self):
        super(long_term_app, self).initialize()
        kill_cmd = DockerCmd(self.parent_subtest, "kill",
                             [self.sub_stuff["container"].long_id],
                             self.config['docker_run_timeout'])

        results = kill_cmd.execute()
        if results.exit_status:
            raise error.TestNAError("Problems during initialization of"
                                    " test: %s", results)

    def postprocess(self):
        super(long_term_app, self).postprocess()
        # Raise exception if problems found
        self.failif(self.sub_stuff['cmdresult'].exit_status != 0,
                    "Non-zero start exit status: %s"
                    % self.sub_stuff['cmdresult'])

        dc = DockerContainersCLIRunOnly(self.parent_subtest)
        running_c = dc.list_containers_with_cid(
            self.sub_stuff["container"].long_id)
        self.failif(running_c == [],
                    "Container with long term task should running.")
