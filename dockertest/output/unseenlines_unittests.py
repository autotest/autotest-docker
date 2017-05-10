#!/usr/bin/env python

import tty
import os
import tempfile
import unittest
import sys
import types


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

setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.utils'), 'PlaceHolder', Exception)


class UnseenLinesTestBase(unittest.TestCase):

    def setUp(self):
        from dockertest.output import UnseenLines
        self.UnseenLines = UnseenLines

    def tearDown(self):
        del self.UnseenLines


class UnseenLinesTestFile(UnseenLinesTestBase):

    def setUp(self):
        super(UnseenLinesTestFile, self).setUp()
        self.tempfile = tempfile.TemporaryFile()
        self.tempfile_fd = self.tempfile.fileno()

    def tearDown(self):
        try:
            del self.tempfile_fd
            del self.tempfile
        except IOError:
            pass
        super(UnseenLinesTestFile, self).tearDown()

    def test_init(self):
        nl = self.UnseenLines(self.tempfile_fd)
        self.assertTrue(nl.idx is not None)
        self.assertTrue(nl.strbuffer is not None)
        self.assertTrue(nl.lines is not None)

    def test_empty(self):
        nl = self.UnseenLines(self.tempfile_fd)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)

    def test_pre_existing(self):
        self.tempfile.write("foo\nbar")
        self.tempfile.flush()
        self.tempfile.seek(0, 0)
        nl = self.UnseenLines(self.tempfile_fd)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.peek(), '')
        self.assertEqual(nl.nextline(), 'foo\n')
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.peek(), 'bar')


class UnseenLinesTestPipe(UnseenLinesTestBase):

    def setUp(self):
        super(UnseenLinesTestPipe, self).setUp()
        self.r_pipe, self.w_pipe = os.pipe()

    def tearDown(self):
        try:
            os.close(self.r_pipe)
            os.close(self.w_pipe)
        except OSError:
            pass
        super(UnseenLinesTestPipe, self).tearDown()

    def test_init(self):
        nl = self.UnseenLines(self.r_pipe)
        self.assertTrue(nl.idx is not None)
        self.assertTrue(nl.strbuffer is not None)
        self.assertTrue(nl.lines is not None)

    def test_empty(self):
        nl = self.UnseenLines(self.r_pipe)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)

    def test_pre(self):
        os.write(self.w_pipe, "foo\nbar")
        nl = self.UnseenLines(self.r_pipe)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.peek(), '')
        self.assertEqual(nl.nextline(), 'foo\n')
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.peek(), 'bar')

    def test_bracketed(self):
        os.write(self.w_pipe, "foo\nbar")
        nl = self.UnseenLines(self.r_pipe)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.peek(), '')
        self.assertEqual(nl.nextline(), 'foo\n')
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.peek(), 'bar')

        os.write(self.w_pipe, "\nbaz")
        self.assertEqual(nl.nextline(), 'bar\n')
        self.assertEqual(nl.peek(), 'baz')
        self.assertEqual(nl.idx, idx + 2)

    def test_post(self):
        nl = self.UnseenLines(self.r_pipe)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)
        os.write(self.w_pipe, "foo\nbar")
        self.assertEqual(nl.peek(), '')
        self.assertEqual(nl.nextline(), 'foo\n')
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.peek(), 'bar')
        self.assertEqual(nl.nextline(), None)


class UnseenLinesTestpty(UnseenLinesTestBase):

    def setUp(self):
        super(UnseenLinesTestpty, self).setUp()
        self.m_pty, self.s_pty = os.openpty()
        tty.setraw(self.m_pty)
        tty.setraw(self.m_pty)

    def tearDown(self):
        try:
            os.close(self.s_pty)
            os.close(self.m_pty)
        except OSError:
            pass
        super(UnseenLinesTestpty, self).tearDown()

    def test_init(self):
        nl = self.UnseenLines(self.s_pty)
        self.assertTrue(nl.idx is not None)
        self.assertTrue(nl.strbuffer is not None)
        self.assertTrue(nl.lines is not None)

    def test_empty(self):
        nl = self.UnseenLines(self.s_pty)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)

    def test_pre(self):
        os.write(self.m_pty, "foo\nbar")
        nl = self.UnseenLines(self.s_pty)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.peek(), '')
        self.assertEqual(nl.nextline(), 'foo\n')
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.peek(), 'bar')

    def test_bracketed(self):
        os.write(self.m_pty, "foo\nbar")
        nl = self.UnseenLines(self.s_pty)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.peek(), '')
        self.assertEqual(nl.nextline(), 'foo\n')
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.peek(), 'bar')

        os.write(self.m_pty, "\nbaz")
        self.assertEqual(nl.nextline(), 'bar\n')
        self.assertEqual(nl.peek(), 'baz')
        self.assertEqual(nl.idx, idx + 2)

    def test_post(self):
        nl = self.UnseenLines(self.s_pty)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)
        os.write(self.m_pty, "foo\nbar")
        self.assertEqual(nl.peek(), '')
        self.assertEqual(nl.nextline(), 'foo\n')
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.peek(), 'bar')
        self.assertEqual(nl.nextline(), None)

# FIXME: Need unittest for UnseenLineMatch

if __name__ == "__main__":
    unittest.main()
