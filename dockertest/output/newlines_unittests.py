#!/usr/bin/env python

import tty
import os
import tempfile
import unittest


class NewLinesTestBase(unittest.TestCase):

    def setUp(self):
        from newlines import NewLines
        self.NewLines = NewLines

    def tearDown(self):
        del self.NewLines


class NewLinesTestFile(NewLinesTestBase):

    def setUp(self):
        super(NewLinesTestFile, self).setUp()
        self.tempfile = tempfile.TemporaryFile()
        self.tempfile_fd = self.tempfile.fileno()

    def tearDown(self):
        try:
            del self.tempfile_fd
            del self.tempfile
        except IOError:
            pass
        super(NewLinesTestFile, self).tearDown()

    def test_init(self):
        nl = self.NewLines(self.tempfile_fd)
        self.assertTrue(nl.idx is not None)
        self.assertTrue(nl.strbuffer is not None)
        self.assertTrue(nl.lines is not None)

    def test_empty(self):
        nl = self.NewLines(self.tempfile_fd)
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
        nl = self.NewLines(self.tempfile_fd)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.peek(), '')
        self.assertEqual(nl.nextline(), 'foo\n')
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx + 1)
        self.assertEqual(nl.peek(), 'bar')


class NewLinesTestPipe(NewLinesTestBase):

    def setUp(self):
        super(NewLinesTestPipe, self).setUp()
        self.r_pipe, self.w_pipe = os.pipe()

    def tearDown(self):
        try:
            os.close(self.r_pipe)
            os.close(self.w_pipe)
        except OSError:
            pass
        super(NewLinesTestPipe, self).tearDown()

    def test_init(self):
        nl = self.NewLines(self.r_pipe)
        self.assertTrue(nl.idx is not None)
        self.assertTrue(nl.strbuffer is not None)
        self.assertTrue(nl.lines is not None)

    def test_empty(self):
        nl = self.NewLines(self.r_pipe)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)

    def test_pre(self):
        os.write(self.w_pipe, "foo\nbar")
        nl = self.NewLines(self.r_pipe)
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
        nl = self.NewLines(self.r_pipe)
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
        nl = self.NewLines(self.r_pipe)
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


class NewLinesTestpty(NewLinesTestBase):

    def setUp(self):
        super(NewLinesTestpty, self).setUp()
        self.m_pty, self.s_pty = os.openpty()
        tty.setraw(self.m_pty)
        tty.setraw(self.m_pty)

    def tearDown(self):
        try:
            os.close(self.s_pty)
            os.close(self.m_pty)
        except OSError:
            pass
        super(NewLinesTestpty, self).tearDown()

    def test_init(self):
        nl = self.NewLines(self.s_pty)
        self.assertTrue(nl.idx is not None)
        self.assertTrue(nl.strbuffer is not None)
        self.assertTrue(nl.lines is not None)

    def test_empty(self):
        nl = self.NewLines(self.s_pty)
        self.assertTrue(nl.idx is not None)
        idx = nl.idx
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)
        self.assertEqual(nl.nextline(), None)
        self.assertEqual(nl.idx, idx)

    def test_pre(self):
        os.write(self.m_pty, "foo\nbar")
        nl = self.NewLines(self.s_pty)
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
        nl = self.NewLines(self.s_pty)
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
        nl = self.NewLines(self.s_pty)
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

# FIXME: Need unittest for NewlineMatch

if __name__ == "__main__":
    unittest.main()
