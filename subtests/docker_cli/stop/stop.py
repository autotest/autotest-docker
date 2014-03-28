"""
Test usage of docker 'stop' command

initialize:
1) start VM with test command
run_once:
2) execute docker stop
postprocess:
3) analyze results
"""
import time

from autotest.client import utils
from dockertest import config, subtest, xceptions
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.subtest import SubSubtest


# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103
class stop(subtest.SubSubtestCaller):
    """ Subtest caller """
    config_section = 'docker_cli/stop'


class stop_base(SubSubtest):
    """ Base class """
    def initialize(self):
        super(stop_base, self).initialize()
        # Prepare a container
        docker_containers = DockerContainers(self.parent_subtest)
        prefix = self.config["stop_name_prefix"]
        name = docker_containers.get_unique_name(prefix, length=4)
        self.sub_stuff['container_name'] = name
        config.none_if_empty(self.config)
        subargs = [arg for arg in self.config['run_options_csv'].split(',')]
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append("bash")
        subargs.append("-c")
        subargs.append(self.config['exec_cmd'])
        container = AsyncDockerCmd(self.parent_subtest, 'run', subargs)
        self.sub_stuff['container_cmd'] = container
        container.execute()
        time.sleep(self.config['wait_start'])
        # Prepare the "stop" command
        subargs = [arg for arg in self.config['stop_options_csv'].split(',')]
        subargs.append(name)
        self.sub_stuff['stop_cmd'] = DockerCmd(self.parent_subtest, 'stop',
                                               subargs)

    def run_once(self):
        # Execute the stop command
        super(stop_base, self).run_once()
        container_cmd = self.sub_stuff['container_cmd']
        self.sub_stuff['stop_results'] = self.sub_stuff['stop_cmd'].execute()
        # Wait for container exit
        for _ in xrange(50):
            if container_cmd.done:
                break
            time.sleep(0.1)
        else:
            raise xceptions.DockerTestFail("Container process did not finish "
                                           "after stop command execution.")
        self.sub_stuff['container_results'] = container_cmd.wait()

    def check_output(self):
        """
        Check that config[check_stdout] is present in the execute docker stdout
        """
        check_stdout = self.config.get("check_stdout")
        results = self.sub_stuff['container_results']
        if check_stdout and check_stdout not in results.stdout:
            raise xceptions.DockerTestFail("Expected stdout '%s' not in "
                                           "container_results:\n%s"
                                           % (check_stdout, results))

    def postprocess(self):
        super(stop_base, self).postprocess()
        self.check_output()
        stop_results = self.sub_stuff['stop_results']
        if self.config.get("stop_duration"):
            stop_duration = float(self.config.get("stop_duration"))
            self.failif(stop_results.duration > (stop_duration + 2),
                        "'docker stop' cmd execution took longer, than "
                        "expected: %ss (%s+-2s)" % (stop_results.duration,
                                               stop_duration))
            self.failif(stop_results.duration < (stop_duration - 2),
                        "'docker stop' cmd execution took shorter, than "
                        "expected: %ss (%s+-2s)" % (stop_results.duration,
                                               stop_duration))
        # Look for docker failures
        OutputGood(stop_results)
        OutputGood(self.sub_stuff['container_results'])
        self.failif(stop_results.exit_status != 0, "Exit status of the docker "
                    "stop command was not 0 (%s)" % stop_results.exit_status)
        self.failif(stop_results.exit_status != 0, "Exit status of the docker "
                    "run command was not 0 (%s)"
                    % self.sub_stuff['container_results'].exit_status)

    def cleanup(self):
        super(stop_base, self).cleanup()
        # In case of internal failure the running container might not finish.
        container_cmd = self.sub_stuff.get('container_cmd')
        if container_cmd and not container_cmd.done:
            utils.signal_pid(container_cmd.process_id, 15)
            if not container_cmd.done:
                utils.signal_pid(container_cmd.process_id, 9)
        if (self.config.get('remove_after_test')
                and self.sub_stuff.get('container_name')):
            args = ['--force', '--volumes', self.sub_stuff['container_name']]
            OutputGood(DockerCmd(self.parent_subtest, 'rm', args).execute())


class nice(stop_base):
    """
    Test usage of docker 'stop' command in case container finishes on SIGTERM

    initialize:
    1) start VM with test command
    run_once:
    2) execute docker stop
    postprocess:
    3) Fail in case SIGTERM was not raised in container
    4) Fail in case stop command execution was too long (SIGKILL was probably
       used)
    """
    pass


class force(stop_base):
    """
    Test usage of docker 'stop' command in case container ignores SIGTERM

    initialize:
    1) start VM with test command
    run_once:
    2) execute docker stop
    postprocess:
    3) Fail in case SIGTERM was not raised in container
    4) Fail in case stop command execution was too short (SIGTERM killed it)
    """
    pass


class stopped(stop_base):
    """
    Test usage of docker 'stop' command in case container is already stopped

    initialize:
    1) start VM with test command
    run_once:
    2) execute docker stop
    postprocess:
    3) Fail in case stop command execution was too long
    """
    pass


class zerotime(stop_base):
    """
    Test usage of docker 'stop' command with -t 0 (should send SIGKILL)

    initialize:
    1) start VM with test command
    run_once:
    2) execute docker stop
    postprocess:
    3) Fail in case SIGTERM was raised in the container
    4) Fail in case stop command execution was too long
    """

    def check_output(self):
        """
        Inverse version of check_output (fails in case of stdout str presence
        """
        check_stdout = self.config.get("check_stdout")
        results = self.sub_stuff['container_results']
        if check_stdout and check_stdout in results.stdout:
            raise xceptions.DockerTestFail("Expected stdout '%s' not in "
                                           "container_results:\n%s"
                                           % (check_stdout, results))
