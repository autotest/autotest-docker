r"""
Summary
---------

Test deferred deletion: device mapper will not delete a docker
filesystem if it's still in use.

This test is only applicable on RHEL 7.4+ systems in which:

  1) kernel is 3.10.0-632 or above; and
  2) The sysctl knob /proc/sys/fs/may_detach_mounts exists and is 1; and
  3) dockerd unit file DOES NOT include MountFlags=slave; and
  4) docker daemon is configured to use devicemapper storage; and
  5) docker daemon is run with --storage-opts dm.use_deferred_deletion=true

As a precondition for running this test, we check only conditions 4 & 5,
aborting with TestNAError if either is false. We trust docker-storage-setup
to only enable #5 if all preconditions are met. Anyone running a system
with 4 & 5 true but 1, 2, or 3 false deserves what they get.

Operational Summary
----------------------

#. Run a docker container
#. Find out the local (host) mountpoint of its root filesystem. cd into it.
#. Read the Deferred-Deletion count from 'docker info'.
#. Remove the container.
#. Read the Deferred-Deletion count; confirm that it has grown by one.
#. cd back out of the container rootfs
#. Read the Deferred-Deletion count; confirm that it has gone back down.

"""

import os
from autotest.client import utils
import dockertest.docker_daemon
from dockertest import subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.images import DockerImage
from dockertest.output import DockerInfo
from dockertest.xceptions import DockerTestNAError


class deferred_deletion(subtest.Subtest):

    def initialize(self):
        super(deferred_deletion, self).initialize()
        dockerinfo = DockerInfo()
        storage_driver = dockerinfo.get('storage_driver')
        self.failif_ne(storage_driver, 'devicemapper',
                       "test only applicable with devicemapper storage driver",
                       DockerTestNAError)

        docker_cmdline = dockertest.docker_daemon.cmdline()
        self.failif_not_in("dm.use_deferred_deletion=true",
                           str(docker_cmdline),
                           "docker daemon command-line options",
                           DockerTestNAError)

        self.stuff['dc'] = DockerContainers(self)

    def run_once(self):
        super(deferred_deletion, self).run_once()

        self._start_idle_container()

        # cd into its directory. This prevents devicemapper from reaping it.
        os.chdir(self._container_mountpoint)

        # Determine baseline count of deferred deletions. We expect 0,
        # but let's not panic if it isn't.
        defer_count_initial = self._defer_count()
        if defer_count_initial != 0:
            self.logwarning("Deferred-Delete count from 'docker info'"
                            " is %d (I expected 0). This may mean your"
                            " system has still-undeleted containers.",
                            defer_count_initial)
        self.stuff['defer_count_initial'] = defer_count_initial

        # Tell the container to exit
        self._stop_idle_container()

    def postprocess(self):
        super(deferred_deletion, self).postprocess()

        defer_count_initial = self.stuff['defer_count_initial']
        self.failif_ne(self._defer_count(),
                       defer_count_initial + 1,
                       "Deferred-Delete count while cd'ed into container")

        # cd out of the container filesystem. devmapper will notice and
        # will clean up, but it may take a while. Allow up to 30 seconds.
        os.chdir('/')
        defer_count_back = lambda: self._defer_count() == defer_count_initial
        self.failif(not utils.wait_for(defer_count_back, timeout=30),
                    "Timed out waiting for Deferred-Delete count (%d) to"
                    " come back down to %d after cd'ing out of container"
                    % (self._defer_count(), defer_count_initial))

    def _start_idle_container(self):
        """
        Start a container. We only need it briefly, until we (the test,
        running in host space) can cd into its root filesystem. Container
        will spin idly until a semaphore file is removed.
        """
        c_name = self.stuff['dc'].get_unique_name()

        fin = DockerImage.full_name_from_defaults(self.config)
        subargs = ['--rm', '--name=' + c_name, fin,
                   'bash -c "echo READY;touch /DELETE-ME;'
                   ' while [ -e /DELETE-ME ]; do sleep 0.1; done"']
        dkrcmd = AsyncDockerCmd(self, 'run', subargs)
        dkrcmd.execute()
        dkrcmd.wait_for_ready(c_name)
        self.stuff['container_name'] = c_name

    def _stop_idle_container(self):
        """
        Stop our idle container, by removing its semaphore file.
        Wait until container is truly gone, as reported by docker ps -a
        """
        os.unlink('DELETE-ME')

        dc = self.stuff['dc']
        c_name = self.stuff['container_name']
        c_gone = lambda: dc.list_containers_with_name(c_name) == []
        self.failif(not utils.wait_for(c_gone, timeout=5),
                    "Timed out waiting for container to exit")
        del self.stuff['container_name']

    @property
    def _container_mountpoint(self):
        """
        Given a container name, return its host-accessible root filesystem
        """
        dc = self.stuff['dc']
        c_name = self.stuff['container_name']
        inspect = dc.json_by_name(c_name)
        d_name = inspect[0]['GraphDriver']['Data']['DeviceName']

        base_path = utils.run('findmnt --noheadings --output TARGET'
                              ' --source /dev/mapper/%s' % d_name)
        mountpoint = os.path.join(base_path.stdout.strip(), 'rootfs')
        self.logdebug('host mount point = %s', mountpoint)
        return mountpoint

    @staticmethod
    def _defer_count():
        """
        Returns the integer count of deferred deletions, as obtained
        from docker info. We assume DockerInfo() is never cached.
        """
        return int(DockerInfo().get('storage_driver',
                                    'deferred_deleted_device_count'))

    def cleanup(self):
        super(deferred_deletion, self).cleanup()
        os.chdir('/')
        if 'container_name' in self.stuff:
            self.stuff['dc'].clean_all(self.stuff['container_name'])
