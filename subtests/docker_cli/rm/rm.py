"""
Test for docker rm subcommand

0. Remember subtest start time
1. Write subtest start time into sub-subtest tmpdir file
2. Share sub-subtest tmpdir to container as volume
3. Container waits for signal to update file in volume
4. Run sub-subtests to exercize 'rm' on container and verify volume file
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import os.path
import time
from autotest.client import utils
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.dockercmd import MustFailDockerCmd
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.containers import DockerContainers

class rm(SubSubtestCaller):
    config_section = 'docker_cli/rm'

    def initialize(self):
        # Fail if any containers are running
        dc = DockerContainers(self, 'cli')
        for cntr in dc.list_containers():
            self.failif('Exit' not in cntr.status,
                        "Container %s found running before test!"
                         % cntr.container_name)
        super(rm, self).initialize()
        # Some common data for static content
        self.stuff['init_time'] = int(time.time())

    def postprocess(self):
        super(rm, self).postprocess()
        dc = DockerContainers(self, 'cli')
        for cntr in dc.list_containers():
            self.failif('Exit' not in cntr.status,
                        "Container %s did not exit!" % cntr.container_name)
class rm_sub_base(SubSubtest):

    def signal_container(self, sig, name):
        self.logdebug("Sending signal %s to %s", sig, name)
        dc = DockerContainers(self.parent_subtest, 'cli')
        return dc.kill_container_by_name(name, sig)

    def finish_container_nicely(self, name):
        sig = self.config['listen_signal']
        self.sub_stuff['pid'] = self.signal_container(sig, name)
        wait_stop = self.config['wait_stop']
        self.logdebug("Waiting up to %d seconds for container to exit",
                      wait_stop)
        self.sub_stuff['dkrcmd'].wait(wait_stop)
        self.logdebug("Exit code was: %s",
                      self.sub_stuff['dkrcmd'].exit_status)

    def try_commit(self, name):
        mfdc = MustFailDockerCmd(self.parent_subtest, 'commit',
                                 [name, 'test_%s' % name])
        cmdresult = mfdc.execute()
        self.failif(cmdresult == 0,
                    "Should not have been able to commit from rm'd container")

    def initialize(self):
        super(rm_sub_base, self).initialize()
        # initial static content
        volume = self.sub_stuff['volume'] = self.tmpdir
        start_filename = os.path.join(volume, 'start')
        self.sub_stuff['start_filename'] = start_filename
        ssfile = open(start_filename, "wb")
        init_time = str(self.parent_subtest.stuff['init_time'])
        ssfile.write(init_time)
        ssfile.close()
        # All run arguments csv from config
        subargs = self.config['run_options_csv'].split(',')
        cntr_name = utils.generate_random_string(8)
        self.sub_stuff['cntr_name'] = cntr_name
        subargs.append("--name=%s" % cntr_name)
        # Bind-mount point on host
        subargs.append("--volume=%s:/workdir" % volume)
        subargs.append("--workdir=/workdir")
        # FQIN is always last
        subargs.append(DockerImage.full_name_from_defaults(self.config))
        subargs.append('/bin/bash')
        subargs.append('-c')
        # Write to a file when signal received
        # Loop forever until marker-file exists
        command = ("\"rm -f stop; trap '/usr/bin/date +%%s.%%N> stop' %s; "
                   "while ! [ -f stop ]; do /usr/bin/sleep 0.1s; done\""
                   % self.config['listen_signal'])
        subargs.append(command)
        # Setup but don't execute docker command
        self.sub_stuff['dkrcmd'] = AsyncDockerCmd(self.parent_subtest,
                                                  'run', subargs)

    def run_once(self):
        super(rm_sub_base, self).run_once()
        self.logdebug("Starting test container with %s",
                       self.sub_stuff['dkrcmd'].command)
        dkrcmd = self.sub_stuff['dkrcmd']
        self.sub_stuff['cmdresult'] = dkrcmd.execute()
        wait_start = self.config['wait_start']
        self.loginfo("Sleeping %d seconds for container to get started",
                      wait_start)
        time.sleep(wait_start)
        # Subclasses will take it from here

    def postprocess(self):
        super(rm_sub_base, self).postprocess()
        name = self.sub_stuff['cntr_name']
        pid = self.sub_stuff['pid']
        self.failif(utils.pid_is_alive(pid), "Container pid %s still alive!"
                                             % pid)
        self.try_commit(name)
        # Check static content is intact and matches expected data
        start_filename = self.sub_stuff['start_filename']
        self.failif(not os.path.isfile(start_filename),
                    "Start file does not exist")
        start_file = open(start_filename, 'rb')
        start_time = int(start_file.read())
        init_time = self.parent_subtest.stuff['init_time']
        self.failif(start_time != init_time,
                    "Static data does not compare, %f != %f"
                    % (start_time, init_time))

class finished(rm_sub_base):
    """
    Signal to update timestamp, exit bash, verify container exit(0), call rm
    """

    def run_once(self):
        super(finished, self).run_once()
        self.finish_container_nicely(self.sub_stuff['cntr_name'])
        # Actual test-subject
        name = self.sub_stuff['cntr_name']
        nfdc = NoFailDockerCmd(self.parent_subtest, 'rm',
                               ['--volumes', name])
        self.sub_stuff['rm_cmdresult'] = nfdc.execute()

    def postprocess(self):
        super(finished, self).postprocess()
        exit_status = self.sub_stuff['cmdresult'].exit_status
        name = self.sub_stuff['cntr_name']
        self.failif(exit_status != 0,
                    "Docker container %s failed to exit!, exit_status %s"
                    % (name, exit_status))

class forced(rm_sub_base):

    def run_once(self):
        super(forced, self).run_once()
        name = self.sub_stuff['cntr_name']
        nfdc = NoFailDockerCmd(self.parent_subtest, 'rm',
                               ['--force', name])
        self.sub_stuff['rm_cmdresult'] = nfdc.execute()

    def postprocess(self):
        self.sub_stuff['pid'] = self.sub_stuff['dkrcmd'].process_id
        wait_stop = self.config['wait_stop']
        self.logdebug("Waiting up to %d seconds for container to be killed",
                      wait_stop)
        self.sub_stuff['dkrcmd'].wait(wait_stop)
        exit_status = self.sub_stuff['cmdresult'].exit_status
        name = self.sub_stuff['cntr_name']
        self.failif(exit_status == 0,
                    "Unexpected container %s clean exit, exit_status %s"
                    % (name, exit_status))
        super(forced, self).postprocess()
