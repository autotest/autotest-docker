r"""
Summary
---------

Test deferred deletion: device mapper should not delete a docker
filesystem if it's still in use.

Operational Summary
----------------------

#. Run a docker container
#. Run a test script inside docker mount space that will:
#. - Find out the local (host) mountpoint of the container's root filesystem.
#. - cd into that directory
#. - Read the Deferred-Deletion count from 'docker info'.
#. - Remove the container.
#. - Read the Deferred-Deletion count; confirm that it has grown by one.
#. - cd back out of the container rootfs
#. - Read the Deferred-Deletion count; confirm that it has gone back down.

Operational Detail
------------------

We need to do all the important work from inside a helper script,
because our autotest process will only have access to the container's
mounts if MountFlags=slave is *absent* from the docker systemd unit file;
by default that option is present, and it is not clear if/when it will be
removed. To make sure we have access to the container's mounts we need
to nsenter the docker daemon's mount namespace, and we can't do that
within autotest (using ctypes.CDLL and setns) because autotest is
multithreaded and setns() doesn't allow that.

Prerequisites
-------------

This test is only applicable if docker daemon is run with:

    --storage-opts dm.use_deferred_deletion=true

(this is detected and enabled by the docker-storage-setup script)

That suffices on Fedora. On RHEL it's more complicated: the 7.2 version
of docker-storage-setup blindly enabled the option even though it
didn't actually work due to a kernel bug. 7.4 introduced a kernel with
a fix, but disabled by default. We therefore need to differentiate
between systems with (1) enabled incorrectly and correctly. We do
so by checking that the sysctl knob /proc/sys/fs/may_detach_mounts
(introduced in kernel 3.10.0-632) exists and is 1.

We abort with TestNAError if any precondition fails.

"""

import os
from autotest.client import utils
import dockertest.docker_daemon
from dockertest import subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.images import DockerImage
from dockertest.output.validate import mustpass
from dockertest.xceptions import DockerTestNAError


class deferred_deletion(subtest.Subtest):

    def initialize(self):
        super(deferred_deletion, self).initialize()

        docker_cmdline = dockertest.docker_daemon.cmdline()
        self.failif_not_in("dm.use_deferred_deletion=true",
                           str(docker_cmdline),
                           "docker daemon command-line options",
                           DockerTestNAError)

        self._rhel72_bug_workaround()

        self.stuff['dc'] = DockerContainers(self)

    def _rhel72_bug_workaround(self):
        """
        On RHEL, docker daemon may be running with deferred_deletion
        enabled incorrectly.
        """

        try:
            self.failif_not_redhat()
        except DockerTestNAError:
            return                   # Fedora or CentOS

        # RHEL
        sysctl_knob = "/proc/sys/fs/may_detach_mounts"
        self.failif(not os.path.exists(sysctl_knob),
                    "sysctl knob %s does not exist; this system is"
                    " not likely to support deferred deletion" % sysctl_knob,
                    DockerTestNAError)

        with open(sysctl_knob, 'rb') as fs_may_detach_mounts:
            enabled = int(fs_may_detach_mounts.read().strip())
            self.failif(not enabled,
                        "sysctl knob %s is '%s'; this test is only valid"
                        " when it is '1'" % (sysctl_knob, enabled),
                        DockerTestNAError)

    def run_once(self):
        super(deferred_deletion, self).run_once()

        self._start_idle_container()

        # Run our testing script
        helper = os.path.join(self.bindir, 'test-deferred-deletion.sh')
        result = utils.run("nsenter -t %d -m %s %s %s"
                           % (dockertest.docker_daemon.pid(), helper,
                              self.stuff['container_name'],
                              self.stuff['trigger_file']),
                           ignore_status=True)
        self.stuff['result'] = result

    def postprocess(self):
        super(deferred_deletion, self).postprocess()
        mustpass(self.stuff['result'])

        # Helper script should be silent; treat any output as a warning
        if self.stuff['result'].stdout:
            self.logwarning(self.stuff['result'].stdout)

    def _start_idle_container(self):
        """
        Start a container. We only need it briefly, until we (the test,
        running in host space) can cd into its root filesystem. Container
        will spin idly until a semaphore file is removed.
        """
        c_name = self.stuff['dc'].get_unique_name()

        fin = DockerImage.full_name_from_defaults(self.config)
        self.stuff['trigger_file'] = trigger_file = 'DELETE-ME'
        subargs = ['--rm', '--name=' + c_name, fin,
                   'bash -c "echo READY;touch /%s;'
                   ' while [ -e /%s ]; do sleep 0.1; done"'
                   % (trigger_file, trigger_file)]
        dkrcmd = AsyncDockerCmd(self, 'run', subargs)
        dkrcmd.execute()
        dkrcmd.wait_for_ready(c_name)
        self.stuff['container_name'] = c_name

    def cleanup(self):
        super(deferred_deletion, self).cleanup()
        if self.config['remove_after_test']:
            if 'container_name' in self.stuff:
                self.stuff['dc'].clean_all([self.stuff['container_name']])
