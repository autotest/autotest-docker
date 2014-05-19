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
import signal
from autotest.client import utils
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest import environment

class rm(SubSubtestCaller):
    config_section = 'docker_cli/rm'

    def initialize(self):
        # Fail if any containers are running
        dc = self.stuff['dc'] = DockerContainers(self, 'cli')
        for cntr in dc.list_containers():
            self.failif('exit' not in cntr.status.lower(),
                        "Container %s found running before test!"
                         % cntr.container_name)
        super(rm, self).initialize()
        # Static data for subtests to use
        self.stuff['init_time'] = int(time.time())


    def postprocess(self):
        super(rm, self).postprocess()
        dc = self.stuff['dc']
        for cntr in dc.list_containers():
            self.failif('Exit' not in cntr.status,
                        "Container %s did not exit!" % cntr.container_name)

    def cleanup(self):
        dc = self.stuff['dc']
        dc.remove_args = '--force --volumes'
        for cnt in dc.list_containers():
            self.logwarning("Removing leftover container: %s", cnt)
            dc.remove_by_obj(cnt)

class rm_sub_base(SubSubtest):

    def rm_container(self, what):
        # Can't use containers module b/c "rm" is the test-subject
        subargs = self.config['rm_options_csv'].strip().split(',')
        subargs.append(what)
        rm_cmd = DockerCmd(self.parent_subtest, 'rm', subargs, verbose=True)
        self.sub_stuff['rm_cmdresult'] = rm_cmd.execute()
        wait_rm = self.config['wait_rm']
        self.loginfo("Sleeping %d seconds after rm",
                      wait_rm)
        time.sleep(wait_rm)

    def signal_container(self, name):
        dc = self.sub_stuff['dc']
        sig = getattr(signal, self.config['listen_signal'])
        self.loginfo("Signaling container %s with %s(%d)",
                     name, self.config['listen_signal'], sig)
        json = dc.json_by_name(name)
        self.failif(not json[0]["State"]["Running"],
                    "Can't signal non-running container, see debug "
                    "log for more detail")
        pid = int(json[0]["State"]["Pid"])
        self.failif(not utils.signal_pid(pid, sig),
                    "Failed to cause container exit with signal: "
                    "still running, see debug log for more detail.")

    def container_finished(self):
        dkrcmd = self.sub_stuff['dkrcmd']
        return dkrcmd.done

    def wait_container(self):
        wait_stop = self.config['wait_stop']
        self.logdebug("Waiting up to %d seconds for container to exit",
                      wait_stop)
        dkrcmd = self.sub_stuff['dkrcmd']
        self.failif(not utils.wait_for(func=self.container_finished,
                                       timeout=wait_stop,
                                       text=("\t\tWaiting for container to "
                                             "exit")),
                    "Container did not exit w/in timeout: stdout '%s' "
                    "stderr '%s'" % (dkrcmd.stdout, dkrcmd.stderr))
        cmdresult = self.sub_stuff['cmdresult'] = dkrcmd.wait()
        self.logdebug("Result: %s", cmdresult)

    def init_static_data(self):
        volume = self.sub_stuff['volume'] = self.tmpdir
        environment.set_selinux_context(volume, "svirt_sandbox_file_t")
        start_filename = os.path.join(volume, 'start')
        self.sub_stuff['start_filename'] = start_filename
        ssfile = open(start_filename, "wb")
        init_time = str(self.parent_subtest.stuff['init_time'])
        ssfile.write(init_time)
        ssfile.close()

    def init_subargs(self):
        dc = self.sub_stuff['dc']
        cntr_name = dc.get_unique_name(self.__class__.__name__)
        self.sub_stuff['cntr_name'] = cntr_name
        subargs = self.config['run_options_csv'].split(',')
        self.sub_stuff['subargs'] = subargs
        subargs.append("--name=%s" % cntr_name)
        # Need to detect when container is running
        cidfile = os.path.join(self.tmpdir, cntr_name)
        self.sub_stuff['cidfile'] = cidfile
        subargs.append("--cidfile=%s" % cidfile)
        subargs.append("--volume=%s:/workdir" % self.sub_stuff['volume'])
        subargs.append("--workdir=/workdir")
        # FQIN is always last
        subargs.append(DockerImage.full_name_from_defaults(self.config))
        subargs.append('/bin/bash')
        subargs.append('-c')
        # Write to a file when signal received
        # Loop forever until marker-file exists
        command = ("\""
                   "echo 'foobar' > stop && "
                   "rm -f stop && trap '/usr/bin/date +%%s> stop' %s && "
                   "while ! [ -f stop ]; do /usr/bin/sleep 0.1s; done"
                    "\""
                   % self.config['listen_signal'])
        subargs.append(command)

    def init_dkrcmd(self):
        subargs = self.sub_stuff['subargs']
        subtest = self.parent_subtest
        self.sub_stuff['dkrcmd'] = AsyncDockerCmd(subtest, 'run', subargs)
        self.logdebug("Initialized command: %s", self.sub_stuff['dkrcmd'])

    def cidfile_has_cid(self):
        """
        Docker ps output updated once container assigned a CID
        """
        cidfile = self.sub_stuff['cidfile']
        if os.path.isfile(cidfile):
            cid = open(cidfile, 'rb').read().strip()
            if len(cid) >= 12:
                self.sub_stuff['container_id'] = cid
                return True
        return False

    def wait_start(self):
        self.sub_stuff['dkrcmd'].execute()
        self.loginfo("Waiting up to %s seconds for container start",
                     self.config['docker_timeout'])
        self.failif(not utils.wait_for(func=self.cidfile_has_cid,
                                       timeout=self.config['docker_timeout'],
                                       text=("\t\tWaiting for container to "
                                             "start")))

    def initialize(self):
        super(rm_sub_base, self).initialize()
        self.sub_stuff['dc'] = self.parent_subtest.stuff['dc']
        self.sub_stuff['init_time'] = self.parent_subtest.stuff['init_time']
        self.sub_stuff['volume'] = None  # host-path to volume
        self.sub_stuff['start_filename'] = None  # volume content filename
        self.sub_stuff['cntr_name'] = None  # name of test container
        self.sub_stuff['cidfile'] = None  # full path to file holding cnt ID
        self.sub_stuff['container_id'] = None  # content of cidfile
        self.sub_stuff['subargs'] = None  # list of docker run arguments
        self.sub_stuff['dkrcmd'] = None  # DockerCmd instance for test
        self.sub_stuff['cmdresult'] = None  # Result of DockerCmd.execute()
        self.sub_stuff['rm_cmdresult'] = None  # Result of docker rm command
        self.init_static_data()
        self.init_subargs()
        self.init_dkrcmd()

    def run_once(self):
        super(rm_sub_base, self).run_once()
        self.wait_start()
        wait_start = self.config['wait_start']
        self.loginfo("Sleeping %d seconds after container start",
                      wait_start)
        time.sleep(wait_start)
        dkrcmd = self.sub_stuff['dkrcmd']
        dkrcmd.update_result()
        self.logdebug("Container status: %s", dkrcmd.cmdresult)
        self.failif(dkrcmd.done, "Container exited before it could be "
                                 "removed.  See debug log for details")

    def verify_output(self):
        cmdresult = self.sub_stuff['cmdresult']
        rm_cmdresult = self.sub_stuff['rm_cmdresult']
        self.failif(cmdresult.exit_status != 0, "Expected zero exit: %s"
                                                % cmdresult)
        self.failif(rm_cmdresult.exit_status != 0, "Expected zero exit: %s"
                                                % rm_cmdresult)
        OutputGood(cmdresult)
        OutputGood(rm_cmdresult)

    def verify_container(self):
        cid = self.sub_stuff['container_id']
        self.loginfo("Verifying container %s is gone", cid)
        cl = self.sub_stuff['dc'].list_containers_with_cid(cid)
        self.failif(cl != [], "Container %s was not removed!" % cid)
        self.loginfo("Container is gone.  Verifying output")

    def verify_start(self):
        # Check static content is intact
        start_filename = self.sub_stuff['start_filename']
        self.failif(not os.path.isfile(start_filename),
                    "Start file does not exist: %s" % start_filename)
        start_file = open(start_filename, 'rb')
        start_time = int(start_file.read())
        init_time = self.sub_stuff['init_time']
        self.failif(start_time != init_time,
                    "Static data does not match, %s != %s"
                    % (start_time, init_time))

    def verify_stop(self):
        stop_filename = os.path.join(self.sub_stuff['volume'], 'stop')
        self.failif(not os.path.isfile(stop_filename),
                    "Stop file does not exist: %s" % stop_filename)
        stop_file = open(stop_filename, 'rb')
        stop_time = int(stop_file.read())
        init_time = self.sub_stuff['init_time']
        self.failif(stop_time <= init_time,
                    "Container stopped before it started, %s <= %s"
                    % (stop_time, init_time))

    def postprocess(self):
        super(rm_sub_base, self).postprocess()
        self.verify_container()
        self.verify_output()
        self.verify_start()
        self.verify_stop()

class finished(rm_sub_base):
    """
    Signal to update timestamp, exit bash, verify container exit(0), call rm
    """

    def run_once(self):
        super(finished, self).run_once()
        cntr_name = self.sub_stuff['cntr_name']
        self.signal_container(cntr_name)
        self.wait_container()
        self.rm_container(cntr_name)

class forced(rm_sub_base):

    def run_once(self):
        super(forced, self).run_once()
        cntr_name = self.sub_stuff['cntr_name']
        self.rm_container(cntr_name)
        self.wait_container()

    def verify_output(self):
        cmdresult = self.sub_stuff['cmdresult']
        rm_cmdresult = self.sub_stuff['rm_cmdresult']
        self.failif(cmdresult.exit_status == 0, "Expected non-zero exit: %s"
                                                % cmdresult)
        self.failif(rm_cmdresult.exit_status != 0, "Expected zero exit: %s"
                                                % rm_cmdresult)
        OutputGood(cmdresult)
        OutputGood(rm_cmdresult)

    def verify_stop(self):
        stop_filename = os.path.join(self.sub_stuff['volume'], 'stop')
        self.failif(os.path.isfile(stop_filename),
                    "Stop file exists, but shouldn't: %s" % stop_filename)
