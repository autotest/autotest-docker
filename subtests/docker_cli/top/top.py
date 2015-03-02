r"""
Summary
---------

Verify output from docker top against a test-controlled container matches
content expectations.

Operational Summary
----------------------

#. start container
#. execute docker top against container
#. verify output
"""

from time import sleep
from time import time
from dockertest.subtest import SubSubtestCaller
from dockertest.subtest import SubSubtest
from dockertest.images import DockerImage
from dockertest.containers import DockerContainers
from dockertest.config import get_as_list
from dockertest.dockercmd import DockerCmd
from dockertest.output import DockerTime


class top(SubSubtestCaller):
    pass


# This abstract base class is not referenced from this module
class base(SubSubtest):  # pylint: disable=R0921

    def init_run_dkrcmd(self):
        # This should probably be non-blocking
        raise NotImplementedError

    def init_top_dkrcmd(self):
        # This should probably be blocking
        raise NotImplementedError

    def get_run_name(self):
        raise NotImplementedError

    # TODO: Make cntnr_state part of container module?
    def cntnr_state(self, name):
        dc = self.sub_stuff['dc']
        json = dc.json_by_name(name)[0]
        state = json['State']
        # Separate representation from implementation
        # (really should use a named tuple)
        return {'running': state['Running'],
                'paused': state['Paused'],
                'restarting': state['Restarting'],
                'oom': state['OOMKilled'],
                'exitcode': state['ExitCode'],
                'error': state['Error'],
                'finished': DockerTime(state['FinishedAt']),
                'started': DockerTime(state['StartedAt']),
                'pid': state['Pid']}

    # TODO: Make is_running_cntnr part of container module?
    def is_running_cntnr(self, name):
        start = time()
        end = start + self.config['docker_timeout']
        while time() < end:
            state = self.cntnr_state(name)
            good = [state['running'] is True,
                    state['paused'] is False,
                    state['restarting'] is False,
                    state['oom'] is False,
                    state['exitcode'] <= 0,
                    state['error'] == "",
                    state['finished'] == DockerTime.UTC.EPOCH,
                    state['started'] > DockerTime.UTC.EPOCH,
                    state['pid'] > 0]
            bad = [state['oom'] is True,
                   state['exitcode'] > 0,
                   state['error'] != "",
                   state['finished'] > DockerTime.UTC.EPOCH]
            if all(good):
                self.logdebug("Container %s confirmed running", name)
                break
            elif any(bad):
                self.logdebug("Container %s has problems %s", name, state)
                break
            else:
                # Don't busy-wait
                sleep(0.1)
        return all(good)

    def initialize(self):
        self.sub_stuff['dc'] = DockerContainers(self)
        fqin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['fqin'] = fqin
        self.sub_stuff['run_options'] = (
            get_as_list(self.config['run_options_csv']))
        self.sub_stuff['run_options'] += ['--name', self.get_run_name()]
        self.sub_stuff['top_options'] = (
            get_as_list(self.config['top_options_csv']))
        self.sub_stuff['containers'] = []
        self.sub_stuff['run_dkrcmd'] = self.init_run_dkrcmd()
        self.sub_stuff['top_dkrcmd'] = self.init_top_dkrcmd()

    def run_once(self):
        self.sub_stuff['run_dkrcmd'].execute()
        self.failif(not self.is_running_cntnr(self.get_run_name()))

    def postprocess(self):
        raise NotImplementedError

    def cleanup(self):
        if self.config['remove_after_test']:
            run_name = self.get_run_name()
            DockerCmd(self, 'kill', [run_name]).execute()
            sleep(1)
            DockerCmd(self, 'rm', ['--force', run_name]).execute()
