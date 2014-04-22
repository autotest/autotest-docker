"""
Test usage of docker 'start' command

initialize:
1) prepare docker container, but don't start it
run_once:
2) execute docker start using the nonexisting name
3) execute the new container using `docker run`
4) execute docker start using the running docker name
5) stop the container
6) execute docker start using the stopped docker name
postprocess:
7) analyze results
"""

from dockertest import config, subtest, xceptions
from dockertest.containers import DockerContainers
from dockertest.dockercmd import (AsyncDockerCmd, NoFailDockerCmd,
                                  MustFailDockerCmd)
from dockertest.images import DockerImage
from dockertest.xceptions import (DockerCommandError, DockerExecError)
from autotest.client.shared import utils


class simple(subtest.SubSubtest):

    def _init_stuff(self):
        """ Initialize stuff """
        self.sub_stuff['container_name'] = None     # name of the container

    def initialize(self):
        super(simple, self).initialize()
        self._init_stuff()
        config.none_if_empty(self.config)
        # Get free name
        prefix = self.config["container_name_prefix"]
        docker_containers = DockerContainers(self.parent_subtest)
        name = docker_containers.get_unique_name(prefix, length=4)
        self.sub_stuff['container_name'] = name

    def _start_container(self, name):
        """ Create, store in self.sub_stuff and execute container """
        self.sub_stuff['container_name'] = name
        if self.config.get('run_options_csv'):
            subargs = [arg for arg in
                       self.config['run_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append("bash")
        subargs.append("-c")
        subargs.append("'echo STARTED: $(date); while :; do sleep 0.1; done'")
        container = AsyncDockerCmd(self.parent_subtest, 'run', subargs)
        container.execute()
        utils.wait_for(lambda: container.stdout.startswith("STARTED"), 5,
                       step=0.1)

    def run_once(self):
        # Execute the start command
        super(simple, self).run_once()
        name = self.sub_stuff['container_name']
        err_msg = ("Start of the %s container failed, but '%s' message is not "
                   "in the output:\n%s")
        # Nonexisting container
        result = MustFailDockerCmd(self.parent_subtest, "start",
                                   [name]).execute()
        self.failif("No such container" not in str(result), err_msg
                    % ("non-existing", 'No such container', result))

        # Running container
        self._start_container(name)
        result = MustFailDockerCmd(self.parent_subtest, "start",
                                   [name]).execute()
        self.failif("is already running" not in str(result), err_msg
                    % ("running", "is already running", result))

        # Stopped container
        NoFailDockerCmd(self.parent_subtest, "kill", [name]).execute()
        result = NoFailDockerCmd(self.parent_subtest, "start",
                                 [name]).execute()

    def postprocess(self):
        super(simple, self).postprocess()
        name = self.sub_stuff['container_name']
        logs = AsyncDockerCmd(self.parent_subtest, "logs", ['-f', name])
        logs.execute()
        utils.wait_for(lambda: logs.stdout.count("\n") == 2, 5, step=0.1)
        out = logs.stdout
        self.failif(out.count("\n") != 2, "The container was executed twice, "
                    "there should be 2 lines with start dates, but is "
                    "%s.\nContainer output:\n%s" % (out.count("\n"), out))
        NoFailDockerCmd(self.parent_subtest, "kill", [name]).execute()

    def cleanup(self):
        super(simple, self).cleanup()
        cleanup_log = []
        name = self.sub_stuff.get('container_name')
        if name and self.config.get('remove_after_test'):
            try:
                NoFailDockerCmd(self.parent_subtest, 'rm',
                                ['--force', '--volumes', name]).execute()
            except (DockerCommandError, DockerExecError), details:
                cleanup_log.append("docker rm failed: %s" % details)
        if cleanup_log:
            msg = "Cleanup failed:\n%s" % "\n".join(cleanup_log)
            self.logerror(msg)  # message is not logged nicely in exc
            raise xceptions.DockerTestError(msg)
