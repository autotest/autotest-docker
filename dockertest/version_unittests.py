#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import unittest, tempfile, shutil, os, sys, types

# DO NOT allow this function to get loose in the wild!
def mock(mod_path):
    """
    Recursivly inject tree of mocked modules from entire mod_path
    """
    name_list = mod_path.split('.')
    child_name = name_list.pop()
    child_mod = sys.modules.get(mod_path, types.ModuleType(child_name))
    if len(name_list) == 0:  # child_name is left-most basic module
        if not sys.modules.has_key(child_name):
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

# Mock module and exception class in one stroke
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)

class VersionTestBase(unittest.TestCase):

    def setUp(self):
        import version
        self.version = version

class VersionTest(VersionTestBase):

    def test_types(self):
        for thing in self.version.MAJOR, self.version.MINOR, self.version.REVIS:
            self.assertTrue(isinstance(thing, int))
        self.assertTrue(isinstance(self.version.FMTSTRING, (str, unicode)))
        self.assertTrue(isinstance(self.version.STRING, (str, unicode)))

    def test_compare_str(self):
        major = self.version.MAJOR
        minor = self.version.MINOR
        revis = self.version.REVIS
        lstr = self.version.STRING
        rstr = (self.version.FMTSTRING % (major, minor, revis+1))
        self.assertEqual(self.version.compare(lstr, rstr), 0)  # equal
        rstr = (self.version.FMTSTRING % (major, minor+1, revis+1))
        self.assertEqual(self.version.compare(lstr, rstr), -1)  # less
        lstr = (self.version.FMTSTRING % (major, minor+10, revis))
        self.assertEqual(self.version.compare(lstr, rstr), 1)  # greater

    def test_compare_tup(self):
        lhs = (1, 0, 0)
        rhs = (1, 0, 0)
        self.assertEqual(self.version.compare(lhs, rhs), 0)  # equal
        rhs = (1, 0, 1)
        self.assertEqual(self.version.compare(lhs, rhs), 0)  # still equal
        lhs = (1, 0, 1)
        self.assertEqual(self.version.compare(lhs, rhs), 0)  # also still equal
        lhs = (0, 100, 0)
        self.assertEqual(self.version.compare(lhs, rhs), -1)  # less
        self.assertEqual(self.version.compare(rhs, lhs), 1)  # greater

if __name__ == '__main__':
    unittest.main()
