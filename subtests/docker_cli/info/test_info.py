# -*- python -*-
#
# Tests for the docker-autotest 'info' subtest
#
# As of 2016-02-12 this only includes verify_pool_name(); we'll try to
# extend coverage as needed.
#
# RUNNING:
#
#   $ nosetests -v subtests/docker_cli/info
#
# This assumes that your autotest-docker is checked out underneath
# the client/tests subdirectory of a checked-out autotest repo,
# *and* that the autotest repo is called "autotest" (e.g. not "my-autotest").
# Also: you can't just run nosetests and hope it'll recurse. It won't.
#
# Yeah. Sorry. There's indubitably a better way. Please fix if you know how.
#
from unittest2 import TestCase, main        # pylint: disable=unused-import
from mock import Mock, patch

import sys
sys.path.append('../../../..')

import info


class TestVerifyPoolName(TestCase):
    # Standard docker pool name to expect
    docker_pool = 'rhel-docker--pool'

    # Typical output from 'dmsetup ls'. Note that order is arbitrary.
    dmsetup_ls = ['rhel-docker--pool	(253:4)',
                  'rhel-swap	(253:1)',
                  'rhel-root	(253:0)',
                  'rhel-docker--pool_tdata	(253:3)',
                  'rhel-docker--pool_tmeta	(253:2)']

    @staticmethod
    def failif(cond, msg):
        if cond:
            raise ValueError(msg)

    def _run_one_test(self, pool_name, dmsetup_output, expected_exception):
        """
        Helper for running an individual test. Creates a set of mocks
        that mimic the behavior we test for but are otherwise NOPs.
        """
        mockinfo = Mock(spec=info.info)
        mockinfo.failif = self.failif
        mockrun = Mock()
        mockrun.stdout = ''.join([line + "\n" for line in dmsetup_output])

        raised = False
        with patch('autotest.client.utils.run', Mock(return_value=mockrun)):
            try:
                info.info.verify_pool_name(mockinfo, pool_name)
            except Exception, e:          # pylint: disable=broad-except
                if expected_exception:
                    # exception message is a more specific check than type
                    self.assertEqual(e.message, expected_exception)
                    raised = True
                else:
                    self.fail("Unexpected exception %s" % e.message)
        if expected_exception and not raised:
            self.fail("Test did not raise expected exception")

    def test_standard_order(self):
        """Expected pool name is the first line of output"""
        self._run_one_test(self.docker_pool, self.dmsetup_ls, None)

    def test_reverse_order(self):
        """Expected pool name is the last line of output"""
        self._run_one_test(self.docker_pool,
                           reversed(self.dmsetup_ls), None)

    def test_empty_dmsetup(self):
        """dmsetup ls produces no output"""
        self._run_one_test(self.docker_pool, [],
                           "'dmsetup ls' reports no docker pools.")

    def test_dmsetup_with_no_pools(self):
        """dmsetup ls contains no lines with the string 'pool'."""
        incomplete = [x for x in self.dmsetup_ls if x.find("pool") < 0]
        self._run_one_test(self.docker_pool, incomplete,
                           "'dmsetup ls' reports no docker pools.")

    def test_pool_missing(self):
        """dmsetup ls contains many lines, but not our desired pool name."""
        incomplete = [x for x in self.dmsetup_ls
                      if not x.startswith(self.docker_pool + "\t")]
        self._run_one_test(self.docker_pool, incomplete,
                           "Docker info pool name 'rhel-docker--pool'"
                           " (from docker info) not found in dmsetup ls"
                           " list '['rhel-docker--pool_tdata',"
                           " 'rhel-docker--pool_tmeta']'")
