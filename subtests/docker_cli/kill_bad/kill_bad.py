"""
Summary
-------
Tests bad signals and good signals to nonexisting containers

Operational Summary
---------------------
#. start container with test command
#. test all ``bad_signals`` using ``docker kill -s $signal $container`` and
   verify it wasn't killed
#. try to kill nonexisting container
"""
import time
from dockertest import config, subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd, AsyncDockerCmd
from dockertest.output import mustfail
from dockertest.images import DockerImage


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
        config.none_if_empty(self.config)
        # Prepare a container
        docker_containers = DockerContainers(self)
        name = docker_containers.get_unique_name()
        self.sub_stuff['container_name'] = name
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
            mustfail(DockerCmd(self, 'kill',
                               ['-s', signal,
                                self.sub_stuff['container_name']],
                               verbose=False).execute(), 1)
            self.failif(self.sub_stuff['container_cmd'].done, "Testing "
                        "container died after using signal %s." % signal)
        dkrcnt = DockerContainers(self)
        nonexisting_name = dkrcnt.get_unique_name()
        self.logdebug("Killing nonexisting containe.")
        mustfail(DockerCmd(self, 'kill', [nonexisting_name],
                           verbose=False).execute(), 1)

    def postprocess(self):
        """
        No postprocess required.
        """
        super(kill_bad_base, self).postprocess()

    def cleanup(self):
        super(kill_bad_base, self).cleanup()
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            dc.clean_all([self.sub_stuff.get("container_name")])


class bad(kill_bad_base):
    pass
