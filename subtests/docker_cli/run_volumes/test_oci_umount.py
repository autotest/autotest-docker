# -*- python -*-
#
# Tests for the docker-autotest oci_umount test (under run_volumes)
#
# This only tests the cross_check_mounts() function, which basically
# returns the intersection between two lists. (More precisely: the
# set of members of one list which contain any substring specified
# in the second).
#
from unittest2 import TestCase, main        # pylint: disable=unused-import
from mock import Mock
import autotest  # pylint: disable=unused-import
import run_volumes


class TestOciUmount(TestCase):

    # Sample list (much abbreviated) taken from a real-world run of findmnt
    # on a container on a system with oci-umount. It should not include
    # any of the oci-umount-managed paths. It is much abbreviated, for
    # reasons of legibility
    real_world_mounted = """/
/proc
/sys
/rootfs
/rootfs/proc
/rootfs/sys
/rootfs/sys/fs/selinux
/rootfs/sys/kernel/debug
/rootfs/run
/rootfs/run/user/0
/rootfs/var/lib/nfs/rpc_pipefs
/etc/resolv.conf
/etc/hosts
/run/secrets
/var/lib/docker""".splitlines()

    real_world_oci_umount_list = """/var/lib/docker/overlay2
/var/lib/docker/overlay
/var/lib/docker/devicemapper
/var/lib/docker/containers
/var/lib/docker-latest/overlay2
/var/lib/docker-latest/overlay
/var/lib/docker-latest/devicemapper
/var/lib/docker-latest/containers
/var/lib/container/storage/lvm
/var/lib/container/storage/devicemapper
/var/lib/container/storage/overlay""".splitlines()

    def _run_one_test(self, mounted, should_not_be_mounted, expect):
        mockinfo = Mock(spec=run_volumes.oci_umount)
        mockinfo.stuff = {}
        mockinfo.stuff['mounted'] = mounted
        mockinfo.stuff['should_not_be_mounted'] = should_not_be_mounted

        actual = run_volumes.oci_umount.cross_check_mounts(mockinfo)
        self.assertEqual(actual, expect)

    def test_basic(self):
        self._run_one_test(['a'], ['b'], [])

    def test_longer_lists(self):
        self._run_one_test(['/a', '/b'], ['/c', '/d'], [])

    def test_one_common(self):
        self._run_one_test(['/a', '/b', '/c'], ['/c', '/d'], ['/c'])

    def test_real_world_ok(self):
        self._run_one_test(self.real_world_mounted,
                           self.real_world_oci_umount_list, [])

    def test_real_world_failure(self):
        extra = ['/rootfs/var/lib/docker/devicemapper']
        mounted = self.real_world_mounted + extra
        self._run_one_test(mounted, self.real_world_oci_umount_list, extra)


if __name__ == '__main__':
    main()
