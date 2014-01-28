#!/usr/bin/env python

import unittest, tempfile, shutil, os, sys

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
