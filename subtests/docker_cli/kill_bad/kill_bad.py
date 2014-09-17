"""
Summary
-------
Tests bad signals and good signals to nonexisting containers

Operation Summary
-----------------
1. start container with test command
2. test all ``bad_signals`` using ``docker kill -s $signal $container`` and
   verify it wasn't killed
3. try to kill nonexisting container
"""
from dockertest import config, xceptions, subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd, MustFailDockerCmd, AsyncDockerCmd
from dockertest.images import DockerImage
import time


class kill_bad(subtest.SubSubtestCaller):

    """ Subtest caller """


class kill_bad_base(subtest.SubSubtest):

    """ Base class """

    def _init_container(self, name):
        """
        Starts container
        """
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
        subargs.append(self.config['exec_cmd'])
        container = AsyncDockerCmd(self, 'run', subargs, verbose=False)
        self.sub_stuff['container_cmd'] = container
        container.execute()

    def initialize(self):
        """
        Runs one container
        """
        super(kill_bad_base, self).initialize()
        # Prepare a container
        docker_containers = DockerContainers(self)
        name = docker_containers.get_unique_name()
        self.sub_stuff['container_name'] = name
        config.none_if_empty(self.config)
        self._init_container(name)
        time.sleep(self.config.get('wait_start', 3))

    def run_once(self):
        """
        Main test body
        """
        super(kill_bad_base, self).run_once()
        self.logdebug("Executing couple of bad kill signals.")
        self.failif(self.sub_stuff['container_cmd'].done, "Testing container "
                    "died unexpectadly.")
        for signal in self.config['bad_signals'].split(','):
            MustFailDockerCmd(self, 'kill',
                              ['-s', signal, self.sub_stuff['container_name']],
                              verbose=False).execute()
            self.failif(self.sub_stuff['container_cmd'].done, "Testing "
                        "container died after using signal %s." % signal)
        dkrcnt = DockerContainers(self)
        nonexisting_name = dkrcnt.get_unique_name()
        self.logdebug("Killing nonexisting containe.")
        MustFailDockerCmd(self, 'kill', [nonexisting_name],
                          verbose=False).execute()

    def postprocess(self):
        """
        No postprocess required (using MustFailDockerCmd in run_once
        """
        super(kill_bad_base, self).postprocess()

    def _cleanup_container(self):
        """
        Cleanup the container
        """
        if self.sub_stuff.get('container_name') is None:
            return  # Docker was not created, we are clean
        containers = DockerContainers(self)
        name = self.sub_stuff['container_name']
        conts = containers.list_containers_with_name(name)
        if conts == []:
            return  # Docker was created, but apparently doesn't exist, clean
        elif len(conts) > 1:
            msg = ("Multiple containers matches name %s, not removing any of "
                   "them...", name)
            raise xceptions.DockerTestError(msg)
        DockerCmd(self, 'rm', ['--force', '--volumes', name],
                  verbose=False).execute()

    def cleanup(self):
        super(kill_bad_base, self).cleanup()
        self._cleanup_container()


class bad(kill_bad_base):
    pass
