# -*- python -*-

from unittest2 import TestCase, main

import imp
import os

results2junit = imp.load_source('results2junit', './results2junit')

# AutotestResults() needs to be cd'ed to the subdirectory containing
# the status file. Poor design decision on my (Ed's) part, fixable,
# but just not worth it right now. Since we run multiple tests, keep
# track of our main directory
BASE_DIR = os.getcwd()

TEST_SUBDIR = 'test_results2junit.d'


class TestSubdir(TestCase):
    def _test_subdir(self, test_name):
        os.chdir(BASE_DIR)
        os.chdir(os.path.join(TEST_SUBDIR, test_name))

        results = results2junit.AutotestResults()
        ts = results2junit.TestSuite(test_name, results)
        xml = ts.as_xml
        expected_xml = open('results.junit', 'r').read()
        self.maxDiff = None
        self.assertEqual(xml, expected_xml)


def test_generator(cwd, name):
    def test(self):
        self._test_subdir(name)
    return test


def subtests():
    return [d for d in os.listdir(TEST_SUBDIR)
            if os.path.isdir(os.path.join(TEST_SUBDIR, d))]


if __name__ == '__main__':
    cwd = os.getcwd()
    for test_name in subtests():
        test_ref = test_generator(cwd, test_name)
        setattr(TestSubdir, "test_" + test_name, test_ref)

    main()
