"""
Summary
---------

Tests relating to namespaces. As of 2016-08-23 only mount namespaces
but it's likely we'll need tests for user namespaces.

Operational Summary
----------------------

#. See individual tests.
"""

from autotest.client import utils
from dockertest import subtest
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtest


class namespaces(subtest.SubSubtestCaller):
    pass


class namespaces_base(SubSubtest):
    pass


class rmdir_mount(namespaces_base):
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

    def initialize(self):
        super(rmdir_mount, self).initialize()

    def run_once(self):
        """
        Run a background container with --rm; while that's running,
        unshare its mount namespace in a longer-running process.
        When the container finishes, we expect the --rm to succeed.
        """
        super(rmdir_mount, self).run_once()
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs = ['--rm', fin, 'bash', '-c', '"echo READY; sleep 15"']
        dkrcmd = AsyncDockerCmd(self, 'run', subargs)
        self.sub_stuff['dkrcmd'] = dkrcmd
        dkrcmd.execute()
        dkrcmd.wait_for_ready(timeout=5)
        self.sub_stuff['unshare'] = utils.run("unshare -m bash -c 'sleep 20'")

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
