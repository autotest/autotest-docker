r"""
Summary
----------

Test usage of docker 'restart' command

Operational Summary
----------------------

#. start container with test command
#. check container output for start message
#. execute docker restart
#. check container output for restart message
#. execute docker stop
#. check container output for stop message
#. analyze results
"""

import time
from dockertest import config, subtest, xceptions
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtest
from dockertest.output import mustpass
from dockertest.dockercmd import DockerCmd


class restart(subtest.SubSubtestCaller):

    """ Subtest caller """
    config_section = 'docker_cli/restart'


class restart_base(SubSubtest):

    """ Base class """

    def initialize(self):
        super(restart_base, self).initialize()
        config.none_if_empty(self.config)
        self.sub_stuff['container_id'] = None
        self.sub_stuff['restart_cmd'] = None
        self.sub_stuff['stop_cmd'] = None
        self.sub_stuff['restart_result'] = None
        self.sub_stuff['stop_result'] = None

        containers = DockerContainers(self)

        # Container
        if self.config.get('run_options_csv'):
            subargs = [arg for arg in
                       self.config['run_options_csv'].split(',')]
        else:
            subargs = []
        image = DockerImage.full_name_from_defaults(self.config)
        subargs.append(image)
        subargs.append("bash")
        subargs.append("-c")
        subargs.append(self.config['exec_cmd'])
        container = DockerCmd(self, 'run', subargs, timeout=240)
        cont_id = mustpass(container.execute()).stdout.strip()
        self.sub_stuff['container_id'] = cont_id
        container = containers.list_containers_with_cid(cont_id)
        if container == []:
            raise xceptions.DockerTestNAError("Fail to get docker with id: %s"
                                              % cont_id)

        # Prepare the "restart" command
        if self.config.get('restart_options_csv'):
            subargs = [arg for arg in
                       self.config['restart_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append(cont_id)
        self.sub_stuff['restart_cmd'] = DockerCmd(self, 'restart', subargs)

        # Prepare the "stop" command
        if self.config.get('stop_options_csv'):
            subargs = [arg for arg in
                       self.config['stop_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append(cont_id)
        self.sub_stuff['stop_cmd'] = DockerCmd(self, 'stop', subargs)

    def check_output(self, lines, bad_lines, timeout=5):
        """
        Wait $timeout for all good lines presence in sub_stuff['container_id']
        :param lines: list of expected lines in given order. All other lines
                      in between are ignored.
        :param bad_lines: list of lines, which musn't be present in the output
        :param timeout: operation deadline
        :raise xceptions.DockerTestFail: In case of bad output or timeout
        :warning: It doesn't wait for input when only bad_lines are given!
        """
        endtime = time.time() + timeout
        container_id = self.sub_stuff['container_id']
        while time.time() < endtime:
            log_results = mustpass(DockerCmd(self, 'logs',
                                             [container_id]).execute())
            log = log_results.stdout.splitlines()
            i = 0   # (good) lines idx
            exp = lines[i]
            for act in log:
                if act in bad_lines:
                    msg = ("Check output fail; all lines present, but "
                           "bad_lines too:\nlines:\n%s\nbad_lines:\n%s\n"
                           "output:\n%s" % (lines, bad_lines, log))
                    raise xceptions.DockerTestFail(msg)
                if exp == act:
                    i += 1
                    if i < len(lines):
                        exp = lines[i]
                    else:
                        exp = None  # lines are done, check only bad_lines...
            if i >= len(lines):
                break
        else:
            msg = ("Check output fail:\ncheck_lines:\n%s\nbad_lines:\n%s\n"
                   "docker_output:\n%s" % (lines, bad_lines, log))
            raise xceptions.DockerTestFail(msg)

    def run_once(self):
        super(restart_base, self).run_once()
        # Wait for init
        self.check_output(self.config.get('start_check', "").split('\\n'),
                          self.config.get('start_badcheck', "").split('\\n'))
        # Restart
        result = mustpass(self.sub_stuff['restart_cmd'].execute())
        self.sub_stuff['restart_results'] = result
        self.check_output(self.config.get('restart_check', "").split('\\n'),
                          self.config.get('restart_badcheck', "").split('\\n'))
        # Stop
        result = mustpass(self.sub_stuff['stop_cmd'].execute())
        self.sub_stuff['stop_results'] = result
        self.check_output(self.config.get('stop_check', "").split('\\n'),
                          self.config.get('stop_badcheck', "").split('\\n'))

    def postprocess(self):
        # Check if execution took the right time (SIGTERM 0s vs. SIGKILL 10s)
        super(restart_base, self).postprocess()
        for check in ("restart", "stop"):
            if self.sub_stuff.get(check + "_duration"):
                result = self.sub_stuff[check + "_results"]
                self.failif(result.duration > check + 3, "Execution of %s took"
                            "longer, than expected. (%s)" % (result.duration,
                                                             check))
                self.failif(result.duration < check - 3, "Execution of %s took"
                            "less, than expected. (%s)" % (result.duration,
                                                           check))

    def cleanup(self):
        # Removes the docker safely
        super(restart_base, self).cleanup()
        if self.sub_stuff.get('container_id') is None:
            return  # Docker was not created, we are clean
        containers = DockerContainers(self)
        cont_id = self.sub_stuff['container_id']
        conts = containers.list_containers_with_cid(cont_id)
        if conts == []:
            return  # Container created, but doesn't exist.  Desired end-state.
        elif len(conts) > 1:
            msg = ("Multiple containers matches id %s, not removing any of "
                   "them...", cont_id)
            raise xceptions.DockerTestError(msg)
        DockerCmd(self, 'rm', ['--force', '--volumes', cont_id]).execute()


class nice(restart_base):

    """
    Test usage of docker 'restart' command (docker exits on SIGTERM)

    initialize:
    1) start container with test command
    run_once:
    2) check container output for start message
    3) execute docker restart, container finishes on SIGTERM
    4) check container output for restart message
    5) execute docker stop, container finishes on SIGTERM
    6) check container output for stop message
    postprocess:
    7) analyze results
    """
    pass


class force(restart_base):

    """
    Test usage of docker 'restart' command (docker exits on SIGTERM)

    initialize:
    1) start container with test command
    run_once:
    2) check container output for start message
    3) execute docker restart, container ignores SIGTERM, finishes on SIGKILL
    4) check container output for restart message
    5) execute docker stop, container ignores SIGTERM, finishes on SIGKILL
    6) check container output for stop message
    postprocess:
    7) analyze results
    """
    pass


class stopped(restart_base):

    """
    Test usage of docker 'restart' command (docker exits on SIGTERM)

    initialize:
    1) start container with test command
    run_once:
    2) wait for container to finish (start message)
    3) execute docker restart
    4) check container output for restart message
    5) execute docker stop (docker is already stopped)
    6) check container output for stop message
    postprocess:
    7) analyze results
    """
    pass


class zerotime(restart_base):

    """
    Test usage of docker 'restart' command (docker exits on SIGTERM)

    initialize:
    1) start container with test command
    run_once:
    2) check container output for start message
    3) execute docker restart without timeout, container should not log
       info about SIGTERM
    4) check container output for restart message
    5) execute docker stop without timeout, container should not log
       info about SIGTERM
    6) check container output for stop message
    postprocess:
    7) analyze results
    """
    pass
