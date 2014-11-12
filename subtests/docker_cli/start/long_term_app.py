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
from start import short_term_app, DockerContainersRunOnly
from dockertest.dockercmd import DockerCmd


class long_term_app(short_term_app):
    config_section = 'docker_cli/start/long_term_app'
    check_if_cmd_finished = False

    def initialize(self):
        super(long_term_app, self).initialize()
        kill_cmd = DockerCmd(self, "kill",
                             [self.sub_stuff["container"].long_id],
                             self.config['docker_run_timeout'])

        results = kill_cmd.execute()
        if results.exit_status:
            raise error.TestNAError("Problems during initialization of"
                                    " test: %s", results)

    def postprocess(self):
        super(long_term_app, self).postprocess()
        # Raise exception if problems found
        cmdresult = self.sub_stuff['dkrcmd'].cmdresult
        self.failif(cmdresult.exit_status != 0,
                    "Non-zero start exit status: %s"
                    % cmdresult)

        dc = DockerContainersRunOnly(self)
        running_c = dc.list_containers_with_cid(
            self.sub_stuff["container"].long_id)
        self.failif(running_c == [],
                    "Container with long term task should running.")
