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

from autotest.client.shared import utils
from dockertest import config, subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest.output import mustpass, mustfail
from dockertest.images import DockerImage


class simple(subtest.SubSubtest):

    def initialize(self):
        super(simple, self).initialize()
        config.none_if_empty(self.config)
        # Get free name
        docker_containers = DockerContainers(self)
        name = docker_containers.get_unique_name()
        self.sub_stuff['container_name'] = name

    def _start_container(self, name):
        """ Create, store in self.sub_stuff and execute container """
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
        container = AsyncDockerCmd(self, 'run', subargs)
        container.execute()
        ok = utils.wait_for(lambda: container.stdout.startswith("STARTED"), 9,
                            step=0.1)
        self.failif(not ok, "Timed out waiting for STARTED from container.\n"
                    "Output: '%s'" % container.stdout)

    def run_once(self):
        # Execute the start command
        super(simple, self).run_once()
        name = self.sub_stuff['container_name']
        # Container does not yet exist; 'start' should fail.
        result = mustfail(DockerCmd(self, "start", [name]).execute(), 1)
        self.failif_not_in(self.config['missing_msg'], str(result),
                           "'docker start <nonexistent container>' failed"
                           " (as expected), but docker error message did not"
                           " include expected diagnostic.")

        # Now run the container. The first "start" here should be a NOP.
        self._start_container(name)
        result = mustpass(DockerCmd(self, "start", [name]).execute())

        # Stop container, then restart it.
        mustpass(DockerCmd(self, "kill", [name]).execute())
        mustpass(DockerCmd(self, "wait", [name]).execute(), 137)
        result = mustpass(DockerCmd(self, "start", [name]).execute())

    def postprocess(self):
        super(simple, self).postprocess()
        name = self.sub_stuff['container_name']
        logs = AsyncDockerCmd(self, "logs", ['-f', name])
        logs.execute()
        ok = utils.wait_for(lambda: logs.stdout.count("\n") == 2, 20, step=0.1)
        self.failif(not ok, "Timed out waiting for second STARTED message.\n"
                    "Output: '%s'" % logs.stdout)
        mustpass(DockerCmd(self, "kill", [name]).execute())

    def cleanup(self):
        super(simple, self).cleanup()
        name = self.sub_stuff.get('container_name')
        if name and self.config.get('remove_after_test'):
            DockerContainers(self).clean_all([name])
