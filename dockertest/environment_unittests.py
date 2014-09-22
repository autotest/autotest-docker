#!/usr/bin/env python

import shutil
import unittest
import tempfile
import os
import os.path

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

class EnvironmentTestBase(unittest.TestCase):

    def setUp(self):
        import environment
        self.environment = environment
        self.tmpdir =  tempfile.mkdtemp(self.__class__.__name__)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        self.assertFalse(os.path.isdir(self.tmpdir))


class TestSubtestDocs(EnvironmentTestBase):

    subtest_docstring = 'Fake docstring'
    subtest_code = '"""\n%s\n"""\n\npass' % subtest_docstring
    subtest_base = 'somedir'
    subtest_path = '%s/subtests' % subtest_base
    subtest_basename = 'fake_subtest'
    subtest_testname = 'another/dir/%s' % subtest_basename
    subtest_fullname = '%s/%s.py' % (subtest_testname, subtest_basename)

    def setUp(self):
        super(TestSubtestDocs, self).setUp()
        self.sd = self.environment.SubtestDocs
        self.subtest_fullpath = os.path.join(self.tmpdir,
                                             self.subtest_path,
                                             self.subtest_fullname)
        subtest_dir = os.path.dirname(self.subtest_fullpath)
        os.makedirs(subtest_dir)
        subtest = open(self.subtest_fullpath, 'wb')
        subtest.write(self.subtest_code)
        subtest.close()

    def test_filenames(self):
        path = os.path.join(self.tmpdir, self.subtest_base)
        filenames = self.environment.SubtestDocs.filenames(path)
        self.assertEqual(len(filenames), 1)
        self.assertEqual(filenames[0], self.subtest_fullpath)

    def test_docstring(self):
        self.assertEqual(self.sd.docstring(self.subtest_fullpath),
                         self.subtest_docstring)

    def test_name(self):
        name = self.sd.name(self.subtest_fullpath)
        self.assertEqual(name, self.subtest_testname)

    def test_str(self):
        self.sd.header_fmt = ''
        self.sd.footer_fmt = ''
        doc = self.sd(self.subtest_fullpath)
        self.assertEqual(doc.strip(), self.subtest_docstring)
        self.assertEqual(doc.find('pass'), -1)

    def test_combined(self):
        self.sd.header_fmt = ''
        self.sd.footer_fmt = ''
        path = os.path.join(self.tmpdir, self.subtest_base)
        doc = self.sd.combined(path)
        self.assertEqual(doc.strip(), self.subtest_docstring)
        self.assertEqual(doc.find('pass'), -1)

    def test_html(self):
        self.sd.header_fmt = ''
        self.sd.footer_fmt = ''
        doc = self.sd(self.subtest_fullpath)
        self.assertEqual(doc.html().strip(),
                         '<p>%s</p>' % self.subtest_docstring)

if __name__ == '__main__':
    unittest.main()
