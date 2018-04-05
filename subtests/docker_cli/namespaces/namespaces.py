"""
Summary
---------

Tests relating to namespaces. As of 2016-08-23 only mount namespaces
but it's likely we'll need tests for user namespaces.

Operational Summary
----------------------

#. See individual tests.
"""

import os
from autotest.client import utils
from dockertest import subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtest


class namespaces(subtest.SubSubtestCaller):
    pass


class rmdir_mount(SubSubtest):
    """
    Motivation for this test was the August 2016 attempt to package
    docker-latest-1.12: the initial builds didn't work, docker daemon
    wouldn't start (various BZs, not important now). The workaround was
    to remove MountFlags=slave from the systemd unit file (1.12.0-5.el7).
    This actually seemed to work fine, and docker-autotest mostly passed,
    but as it turns out that workaround would've triggered problems in
    the field. This test is an attempt to catch one such problem. It
    passes on docker-latest-1.12.0-12.el7, fails if docker is run
    without MountFlags=slave. See rhbz1347821 for further info.
    """

    def run_once(self):
        """
        Run a background container with --rm; while that's running, clone
        another process sharing the same mount namespace. That process
        will signal the container to finish, and when docker cleans it
        up (--rm) we expect no errors.
        """
        super(rmdir_mount, self).run_once()
        fin = DockerImage.full_name_from_defaults(self.config)
        name = DockerContainers(self).get_unique_name()

        # Create a state file; container will exit once this is deleted
        waitfile = 'state_file_for_signaling_the_container_to_exit'
        waitfile_local = os.path.join(self.tmpdir, waitfile)
        open(waitfile_local, 'a').close()

        # Basically: mount self.tmpdir as /tmp in container, constantly
        # check the state file, exit when it's deleted, then (--rm) have
        # docker clean it up.
        subargs = ['--rm', '-v', '%s:/tmp:z' % self.tmpdir,
                   '--name', name, fin,
                   'bash', '-c',
                   "'echo READY; while [ -e /tmp/%s ]; do sleep 0.1; done'"
                   % waitfile]
        dkrcmd = AsyncDockerCmd(self, 'run', subargs)
        self.sub_stuff['dkrcmd'] = dkrcmd
        dkrcmd.execute()
        dkrcmd.wait_for_ready(name)

        # Container is running. Now, in parallel: clone, delete state file,
        # and wait for container to terminate.
        in_n = ("rm -f %s;"
                " while :;do"
                "   docker inspect %s 2>/dev/null || exit 0;"
                " done" % (waitfile_local, name))
        self.sub_stuff['unshare'] = utils.run("unshare -m bash -c '%s'" % in_n)

    def postprocess(self):
        """
        If the bug triggers, we'll see:
          Error response from daemon: Unable to remove filesystem for <sha>:
             remove /var/lib/docker-latest/containers/<sha>/shm:
             device or resource busy
        """
        super(rmdir_mount, self).postprocess()
        self.failif_ne(self.sub_stuff['dkrcmd'].stderr, '',
                       'stderr from docker command')
        self.failif_ne(self.sub_stuff['unshare'].stderr, '',
                       'unexpected stderr from unshare command')
