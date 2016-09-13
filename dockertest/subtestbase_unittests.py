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
    Recursivly inject tree of mocked modules from entire mod_path
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

    def test_failif_not_redhat(self):
        with open(self.stbsb.redhat_release_filepath, 'wb') as rhrel:
            rhrel.write('this is not a red hat system')
        self.assertRaises(DockerTestFail, self.stbsb.failif_not_redhat,
                          DockerTestFail)

    def test_failif_redhat(self):
        with open(self.stbsb.redhat_release_filepath, 'wb') as rhrel:
            rhrel.write('Red Hat Enterprise Linux Atomic Host release 7.2')
        self.assertEqual(self.stbsb.failif_not_redhat(DockerTestFail), None)


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
