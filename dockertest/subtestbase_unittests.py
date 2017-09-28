#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import os
import sys
from tempfile import mkstemp
import types
from unittest2 import TestCase, main


###############################################################################
# BEGIN boilerplate crap needed for subtests, which should be refactored

# DO NOT allow this function to get loose in the wild!
def mock(mod_path):
    """
    Recursively inject tree of mocked modules from entire mod_path
    """
    name_list = mod_path.split('.')
    child_name = name_list.pop()
    child_mod = sys.modules.get(mod_path, types.ModuleType(child_name))
    if len(name_list) == 0:  # child_name is left-most basic module
        if child_name not in sys.modules:
            sys.modules[child_name] = child_mod
        return sys.modules[child_name]
    else:
        # New or existing child becomes parent
        recurse_path = ".".join(name_list)
        parent_mod = mock(recurse_path)
        if not hasattr(sys.modules[recurse_path], child_name):
            setattr(parent_mod, child_name, child_mod)
            # full-name also points at child module
            sys.modules[mod_path] = child_mod
        return sys.modules[mod_path]


class DockerTestFail(Exception):

    """ Fake class for errors """
    pass

# Mock module and exception class in one stroke
setattr(mock('xceptions'), 'DockerTestFail', DockerTestFail)
setattr(mock('xceptions'), 'DockerTestNAError', DockerTestFail)
# Avoids import error
mock('autotest.client.utils')

# END   boilerplate crap needed for subtests, which should be refactored
###############################################################################

# In each of these, the left-hand string(s) will be present at right.
expect_pass = [
    ['a',        'a'],
    ['a',        'aa'],
    ['a',        'abc'],
    ['a',        'cba'],
    ['a|a',      'a'],
    ['a | a',    'a'],
    ['string',   'ceci nest pas une string'],
    ['no|yes',   'googlyeyes'],
    ['no | yes', 'googlyeyes'],
    ['needle',   'needle in a haystack'],
    ['needle',   'haystack with a needle in the middle'],
    ['needle',   'haystack with, at end, a needle'],
]

# The left-hand string(s) will NOT be in the right
expect_fail = [
    ['a',         'b'],
    ['needle',    'haystack'],
    ['a|b|c',     'd'],
    ['a | b | c', 'd'],
    ['a | a | a', 'b'],
]


class TestNotRedHat(TestCase):

    def setUp(self):
        import subtestbase
        self.subtestbase = subtestbase
        # Saves some typing
        self.stbsb = self.subtestbase.SubBase
        pfx = 'subtestbase_unitest'
        (fd,
         self.stbsb.redhat_release_filepath) = mkstemp(prefix=pfx)
        os.close(fd)

    def tearDown(self):
        os.unlink(self.stbsb.redhat_release_filepath)

    def test_failif_not_redhat(self):
        with open(self.stbsb.redhat_release_filepath, 'wb') as rhrel:
            rhrel.write('this is not a red hat system')
        self.assertRaises(DockerTestFail, self.stbsb.failif_not_redhat,
                          DockerTestFail)

    def test_failif_redhat(self):
        with open(self.stbsb.redhat_release_filepath, 'wb') as rhrel:
            rhrel.write('Red Hat Enterprise Linux Atomic Host release 7.2')
        self.assertEqual(self.stbsb.failif_not_redhat(DockerTestFail), None)


class TestIsKnownFailure(TestCase):
    """
    Tests for is_known_failure()
    """

    # Default contents for the known_failures.txt file
    known_failures = """
docker-1.12.6-4.fc24.x86_64  docker_cli/mysubtest         random reason 1
docker-1.12.6-5.fc24.x86_64  docker_cli/mysubtest/subsub  random reason 2
docker-1.12.4-*              docker_cli/othersubtest      fixed in 1.12.5

# Blank lines and comment lines are ok
"""

    def setUp(self):
        import subtestbase
        self.subtestbase = subtestbase
        self.stbsb = self.subtestbase.SubBase()
        self.tmpfile = None

    def tearDown(self):
        if self.tmpfile:
            os.unlink(self.tmpfile)

    def write_known_failures_file(self, content=known_failures):
        """
        Create a tempfile containing our known failures list. Override the
        known_failures_file() function so it returns a path to this file.
        """
        if self.tmpfile:
            return               # Don't overwrite existing file

        fd, path = mkstemp(prefix='subtestbase-unittest-')
        os.close(fd)
        with open(path, 'w') as fh:
            fh.write(content)
        self.tmpfile = path
        self.subtestbase.known_failures_file = lambda: path

    def _run_test(self, subtest, nvra, expected_status, expected_warnings):
        """
        Basic helper for individual tests. Sets up an environment with
        a known_failures_file, a given nvra, a given subtest, then
        confirms that is_known_failure() returns the expected True/False
        value and that it emits the expected warning messages (if any).
        """
        self.write_known_failures_file()
        self.subtestbase.docker_rpm = lambda: nvra
        self.stbsb.config_section = subtest

        # is_known_failure() returns only True/False, but it will log
        # diagnostic messages. Trap those here, so we can compare against
        # expectations.
        warnings = [[]]
        def log_warnings(msg):
            warnings[0].append(msg)
        setattr(mock('logging'), 'warn', log_warnings)

        # Run the test. Compare status, then messages.
        self.assertEqual(self.stbsb.is_known_failure(), expected_status)
        if expected_warnings:
            expected_warnings = "\tSubBase: " + expected_warnings
            self.assertEqual([expected_warnings.format(**locals())],
                             warnings[0],
                             "diagnostic messages from is_known_failure")
        else:
            self.assertEqual([], warnings[0],
                             "is_known_failure() should produce no warnings")

    def test_known_subtest(self):
        """
        Basic test: NVRA and subtest are explicitly listed as failures.
        """
        self._run_test('docker_cli/mysubtest',
                       'docker-1.12.6-4.fc24.x86_64',
                       True,
                       '{subtest}: Known failure on {nvra}: random reason 1')

    def test_known_subsubtest(self):
        """
        Basic test: NVRA and sub-subtest are explicitly listed as failures.
        Note that we don't actually invoke is_known_failure() with a
        subsubtest arg, the cost/benefit of that isn't worth it.
        """
        self._run_test('docker_cli/mysubtest/subsub',
                       'docker-1.12.6-5.fc24.x86_64',
                       True,
                       '{subtest}: Known failure on {nvra}: random reason 2')

    def test_known_fail_other_builds(self):
        """
        Not a known failure, but test that we get a helpful warning.
        """
        self._run_test('docker_cli/mysubtest',
                       'docker-1.12.6-5.fc24.x86_64',
                       False,
                       '{subtest} is known to fail in other docker-1.12.6 builds')

    def test_known_fail_other_minor_version(self):
        """
        Not a known failure, but test that we get a helpful warning.
        """
        self._run_test('docker_cli/mysubtest',
                       'docker-1.12.7-1.fc24.x86_64',
                       False,
                       '{subtest} is known to fail in other '
                       'docker-1.12.x builds')

    def test_known_fail_all_builds(self):
        """
        Test wildcards: all known builds of 1.12.4-* are expected to fail.
        """
        self._run_test('docker_cli/othersubtest',
                       'docker-1.12.4-1.fc24.x86_64',
                       True,
                       '{subtest} expected to fail on all builds of '
                       'docker-1.12.4: fixed in 1.12.5')

    def test_not_known_subtest(self):
        """
        Subtest is not in the list: no diagnostics issued.
        """
        self._run_test('docker_cli/subtestnotinthelist',
                       'docker-1.12.6-5.fc24.x86_64',
                       False,
                       None)

    def test_not_known_failure(self):
        """
        Subtest is on the list, but not for this N-V
        """
        self._run_test('docker_cli/mysubtest',
                       'docker-1.13.1-1.fc24.x86_64',
                       False,
                       None)

    def test_missing_input_file(self):
        """
        Missing known_failures_file should issue a warning but not fail
        """
        self.write_known_failures_file()
        os.unlink(self.tmpfile)
        self._run_test('doesnt/matter', 'docker-1.2.3-4.fc5', False,
                       "Skipping known_failure check: [Errno 2]"
                       " No such file or directory: '%s'" % self.tmpfile)
        self.tmpfile = None

    def test_bad_row_ok(self):
        """
        Bad input lines should be ignored with a warning
        """
        self.write_known_failures_file("a b\n" + self.known_failures)
        self._run_test('doesnt/matter', 'docker-1.2.3-4.fc5', False,
                       "Bad row in %s: a b" % self.tmpfile)


class TestFailIfNotIn(TestCase):
    """
    Tests for failif_not_in()
    """
    pass


# Generate tests for each case:
#  https://stackoverflow.com/questions/32899/how-to-generate-dynamic-parametrized-unit-tests-in-python
def test_generator_pass(needle, haystack):
    def test(self):
        import subtestbase
        subtestbase.SubBase.failif_not_in(needle, haystack)
    return test


def test_generator_fail(needle, haystack):
    def test(self):
        import subtestbase
        self.assertRaises(DockerTestFail,
                          subtestbase.SubBase.failif_not_in,
                          needle, haystack)
    return test

if __name__ == '__main__':
    for t in expect_pass:
        test_name = filter(lambda c: c.isalpha() or c == '_',
                           'test_%s__in__%s' % (t[0], t[1]))
        test_ref = test_generator_pass(t[0], t[1])
        setattr(TestFailIfNotIn, test_name, test_ref)

    for t in expect_fail:
        test_name = filter(lambda c: c.isalpha() or c == '_',
                           'test_%s__not_in__%s' % (t[0], t[1]))
        test_ref = test_generator_fail(t[0], t[1])
        setattr(TestFailIfNotIn, test_name, test_ref)

    main()
