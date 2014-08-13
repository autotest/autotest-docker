"""
Test usage of docker 'wait' command

initialize:
1) starts all containers defined in containers
2) prepares the wait command
3) prepares the expected results
run_once:
4) executes the test command in all containers
5) executes the wait command
6) waits until all containers should be finished
postprocess:
7) analyze results
"""
import random
import re
import time

from dockertest import config, subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd, NoFailDockerCmd
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.subtest import SubSubtest
from dockertest.xceptions import (DockerTestFail, DockerOutputError,
                                  DockerTestError, DockerTestNAError)


class wait(subtest.SubSubtestCaller):

    """ Subtest caller """
    config_section = 'docker_cli/wait'


class wait_base(SubSubtest):

    """ Base class """
    re_sleep = re.compile(r'sleep (\d+)')
    re_exit = re.compile(r'exit (\d+)')

    # TODO: Check other tests/upcoming tests, add to config module?
    def get_object_config(self, obj_name, key, default=None):
        return self.config.get(key + '_' + obj_name,
                               self.config.get(key, default))

    def init_substuff(self):
        # sub_stuff['containers'] is list of dicts containing:
        # 'result' - DockerCmd process (detached)
        # 'id' - id or name of the container
        # 'exit_status' - expected exit code after test command
        # 'test_cmd' - AsyncDockerCmd of the test command (attach ps)
        # 'test_cmd_stdin' - stdin used by 'test_cmd'
        # 'sleep_time' - how long it takes after test_cmd before exit
        self.sub_stuff['containers'] = []
        self.sub_stuff['wait_cmd'] = None
        self.sub_stuff['wait_stdout'] = None    # Expected wait stdout output
        self.sub_stuff['wait_stderr'] = None    # Expected wait stderr output
        self.sub_stuff['wait_result'] = None
        self.sub_stuff['wait_duration'] = None  # Wait for tested conts
        self.sub_stuff['wait_should_fail'] = None   # Expected wait failure
        # Sleep after wait finishes (for non-tested containers to finish
        self.sub_stuff['sleep_after'] = None

    def init_container(self, name):
        subargs = self.get_object_config(name, 'run_options_csv')
        if subargs:
            subargs = [arg for arg in
                       self.config['run_options_csv'].split(',')]
        else:
            subargs = []
        image = DockerImage.full_name_from_defaults(self.config)
        subargs.append(image)
        subargs.append("bash")
        cont = {'result': DockerCmd(self, 'run', subargs, 10)}
        self.sub_stuff['containers'].append(cont)
        cont_id = cont['result'].execute().stdout.strip()
        cont['id'] = cont_id

        # Cmd must contain one "exit $exit_status"
        cmd = self.get_object_config(name, 'exec_cmd')
        cont['exit_status'] = self.re_exit.findall(cmd)[0]
        sleep = self.re_sleep.findall(cmd)
        if sleep:
            sleep = int(sleep[0])
            cont['sleep_time'] = sleep
        else:
            cont['sleep_time'] = 0
        cont['test_cmd'] = AsyncDockerCmd(self, "attach", [cont_id])
        cont['test_cmd_stdin'] = cmd

    def init_use_names(self, use_names=False):
        if use_names:
            conts = self.sub_stuff['containers']
            containers = DockerContainers(self.parent_subtest)
            containers = containers.list_containers()
            cont_ids = [cont['id'] for cont in conts]
            for cont in containers:
                if cont.long_id in cont_ids:
                    if use_names is not True and random.choice((True, False)):
                        continue    # 50% chance of using id vs. name
                    # replace the id with name
                    cont_idx = cont_ids.index(cont.long_id)
                    conts[cont_idx]['id'] = cont.container_name

    def init_wait_for(self, wait_for, subargs):
        if not wait_for:
            raise DockerTestNAError("No container specified in config. to "
                                    "wait_for.")
        conts = self.sub_stuff['containers']
        end = False
        wait_duration = 0
        wait_stdout = []
        wait_stderr = []

        for cont in wait_for.split(' '):  # digit or _$STRING
            if cont.isdigit():
                cont = conts[int(cont)]
                subargs.append(cont['id'])
                wait_stdout.append(cont['exit_status'])
                wait_duration = max(wait_duration, cont['sleep_time'])
            else:
                subargs.append(cont[1:])
                msg = ("Error response from daemon: wait: no such container: "
                       "%s" % cont[1:])
                wait_stderr.append(msg)
                end = True
        self.sub_stuff['wait_stdout'] = '\n'.join(wait_stdout)
        self.sub_stuff['wait_stderr'] = '\n'.join(wait_stderr)
        self.sub_stuff['wait_should_fail'] = end
        self.sub_stuff['wait_duration'] = wait_duration
        self.sub_stuff['wait_cmd'] = DockerCmd(self, 'wait', subargs,
                                               wait_duration + 20)
        max_duration = max(conts, key=lambda x: x['sleep_time'])['sleep_time']
        self.sub_stuff['sleep_after'] = max(0, max_duration - wait_duration)

    def prep_wait_cmd(self, wait_options_csv=None):
        if wait_options_csv is not None:
            subargs = [arg for arg in
                       self.config['wait_options_csv'].split(',')]
        else:
            subargs = []
        self.init_wait_for(self.config['wait_for'], subargs)

    def initialize(self):
        super(wait_base, self).initialize()
        config.none_if_empty(self.config)
        self.init_substuff()

        # Container
        for name in self.config['containers'].split():
            self.init_container(name)

        self.init_use_names(self.config.get('use_names', False))

        # Prepare the "wait" command
        self.prep_wait_cmd(self.config.get('wait_options_csv'))

    def run_once(self):
        super(wait_base, self).run_once()
        for cont in self.sub_stuff['containers']:
            self.logdebug("Executing %s, stdin %s", cont['test_cmd'],
                          cont['test_cmd_stdin'])
            cont['test_cmd'].execute(cont['test_cmd_stdin'] + "\n")
        result = self.sub_stuff['wait_cmd'].execute()
        self.sub_stuff['wait_results'] = result
        self.logdebug("Wait finished, sleeping for %ss for non-tested "
                      "containers to finish.", self.sub_stuff['sleep_after'])
        time.sleep(self.sub_stuff['sleep_after'])

    def postprocess(self):
        # Check if execution took the right time (SIGTERM 0s vs. SIGKILL 10s)
        super(wait_base, self).postprocess()
        result = self.sub_stuff['wait_results']

        self.failif(self.sub_stuff['wait_stdout'] not in result.stdout,
                    "Expected: \n%s\n"
                    "in stdout:\n%s" % (self.sub_stuff['wait_stdout'],
                                        result.stdout))
        self.failif(self.sub_stuff['wait_stderr'] not in result.stderr,
                    "Expected: \n%s\n"
                    "in stderr:\n%s" % (self.sub_stuff['wait_stderr'],
                                        result.stderr))
        if self.sub_stuff['wait_should_fail']:
            try:
                OutputGood(result)
                raise DockerTestFail("Wait command should have failed but "
                                     "passed instead: %s" % result)
            except DockerOutputError:
                self.failif(result.exit_status == 0, "Wait exit_status should "
                            "be non-zero, but in fact is 0")
        else:
            OutputGood(result)
            self.failif(result.exit_status != 0, "Wait exit_status should be "
                        "zero, but is %s instead" % result.exit_status)
        exp = self.sub_stuff['wait_duration']
        self.failif(result.duration > exp + 3, "Execution of wait took longer,"
                    " than expected. (%s %s+-3s)" % (result.duration, exp))
        self.failif(result.duration < exp - 3, "Execution of wait took less, "
                    "than expected. (%s %s+-3s)" % (result.duration, exp))
        for cmd in (cont['test_cmd'] for cont in self.sub_stuff['containers']):
            self.failif(not cmd.done, "Wait passed even thought one of the "
                        "test commands execution did not finish...\n%s")
            OutputGood(cmd.wait(0))

    def cleanup(self):
        # Removes the docker safely
        failures = []
        super(wait_base, self).cleanup()
        if not self.sub_stuff.get('containers'):
            return  # Docker was not created, we are clean
        containers = DockerContainers(self.parent_subtest).list_containers()
        test_conts = self.sub_stuff.get('containers')
        for cont in test_conts:
            if 'id' not in cont:  # Execution failed, we don't have id
                failures.append("Container execution failed, can't verify what"
                                "/if remained in system: %s"
                                % cont['result'])
            if 'test_cmd' in cont:
                if not cont['test_cmd'].done:
                    try:
                        cont['test_cmd'].wait(0)
                    except Exception, details:
                        failures.append("Test cmd %s had to be killed: %s"
                                        % (cont['test_cmd'], details))
        cont_ids = [cont['id'] for cont in test_conts]
        for cont in containers:
            if cont.long_id in cont_ids or cont.container_name in cont_ids:
                try:
                    NoFailDockerCmd(self, 'rm',
                                    ['--force', '--volumes', cont.long_id]
                                    ).execute()
                except Exception, details:
                    failures.append("Fail to remove container %s: %s"
                                    % (cont.long_id, details))
        if failures:
            raise DockerTestError("Cleanup failed:\n%s" % failures)


class no_wait(wait_base):

    """
    Test usage of docker 'wait' command (waits only for containers, which
    should already exited. Expected execution duration is 0s)

    initialize:
    1) starts all containers defined in containers
    2) prepares the wait command
    3) prepares the expected results
    run_once:
    4) executes the test command in all containers
    5) executes the wait command
    6) waits until all containers should be finished
    postprocess:
    7) analyze results
    """
    pass


class wait_first(wait_base):

    """
    Test usage of docker 'wait' command (first container exits after 10s,
    others immediately. Expected execution duration is 10s)

    initialize:
    1) starts all containers defined in containers
    2) prepares the wait command
    3) prepares the expected results
    run_once:
    4) executes the test command in all containers
    5) executes the wait command
    6) waits until all containers should be finished
    postprocess:
    7) analyze results
    """
    pass


class wait_last(wait_base):

    """
    Test usage of docker 'wait' command (last container exits after 10s,
    others immediately. Expected execution duration is 10s)

    initialize:
    1) starts all containers defined in containers
    2) prepares the wait command
    3) prepares the expected results
    run_once:
    4) executes the test command in all containers
    5) executes the wait command
    6) waits until all containers should be finished
    postprocess:
    7) analyze results
    """
    pass


class wait_missing(wait_base):

    """
    Test usage of docker 'wait' command (first and last containers doesn't
    exist, second takes 10s to finish and the rest should finish immediately.
    Expected execution duration is 10s with 2 exceptions)

    initialize:
    1) starts all containers defined in containers
    2) prepares the wait command
    3) prepares the expected results
    run_once:
    4) executes the test command in all containers
    5) executes the wait command
    6) waits until all containers should be finished
    postprocess:
    7) analyze results
    """
    pass
