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

from dockertest import config, subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest.output import mustpass, mustfail
from dockertest.images import DockerImage
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
        docker_containers = DockerContainers(self)
        name = docker_containers.get_unique_name()
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
        container = AsyncDockerCmd(self, 'run', subargs)
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
        missing_msg = self.config['missing_msg']
        result = mustfail(DockerCmd(self, "start", [name]).execute(), 125)
        self.failif(missing_msg not in str(result), err_msg
                    % ("non-existing", missing_msg, result))

        # Running container
        self._start_container(name)
        result = mustpass(DockerCmd(self, "start", [name]).execute())

        # Stopped container
        mustpass(DockerCmd(self, "kill", [name]).execute())
        result = mustpass(DockerCmd(self, "start", [name]).execute())

    def postprocess(self):
        super(simple, self).postprocess()
        name = self.sub_stuff['container_name']
        logs = AsyncDockerCmd(self, "logs", ['-f', name])
        logs.execute()
        utils.wait_for(lambda: logs.stdout.count("\n") == 2, 5, step=0.1)
        out = logs.stdout
        self.failif(out.count("\n") != 2, "The container was executed twice, "
                    "there should be 2 lines with start dates, but is "
                    "%s.\nContainer output:\n%s" % (out.count("\n"), out))
        mustpass(DockerCmd(self, "kill", [name]).execute())

    def cleanup(self):
        super(simple, self).cleanup()
        name = self.sub_stuff.get('container_name')
        if name and self.config.get('remove_after_test'):
            DockerContainers(self).clean_all([name])
