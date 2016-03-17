#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import sys
import types
import unittest
import time
import random


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


def wait_for(func, timeout, first=0, step=1, text=None):
    end_time = time.time() + timeout

    time.sleep(first)

    while time.time() < end_time:
        output = func()
        if output:
            return output

        time.sleep(step)

    return None

# Mock module and exception class in one stroke
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)
setattr(mock('autotest.client.utils'), 'wait_for', wait_for)


class FakeCmdResult(object):

    def __init__(self, command, exit_status=0,
                 stdout='', stderr='', duration=0):
        self.command = command
        self.exit_status = exit_status
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration


class BaseInterfaceTest(unittest.TestCase):

    def setUp(self):
        import output
        from xceptions import DockerOutputError
        self.output = output
        self.DockerOutputError = DockerOutputError
        self.good_cmdresult = FakeCmdResult('/bin/true', exit_status=0)
        self.bad_cmdresult = FakeCmdResult('/bin/false', exit_status=1)

    def test_no_checks_good(self):
        for cmdresult in (self.good_cmdresult, self.bad_cmdresult):
            self.assertTrue(self.output.OutputGoodBase(cmdresult,
                                                       ignore_error=False))
            self.assertTrue(self.output.OutputGoodBase(cmdresult,
                                                       ignore_error=True))

    # Following cases create classes with fake self pylint: disable=E0213
    def test_all_good(self):
        class all_good(self.output.OutputGoodBase):

            def good_check(fake_self, output):
                return True
        for cmdresult in (self.good_cmdresult, self.bad_cmdresult):
            self.assertTrue(all_good(cmdresult, ignore_error=False))
            self.assertTrue(all_good(cmdresult, ignore_error=True))

    def test_multi_actual(self):
        class Actual(self.output.OutputGoodBase):

            def good_check(fake_self, output):
                return True

            def actual_check(fake_self, output):
                return fake_self.cmdresult.exit_status == 0
        self.assertTrue(Actual(self.good_cmdresult, ignore_error=True))
        self.assertFalse(Actual(self.bad_cmdresult, ignore_error=True))
        self.assertRaises(self.DockerOutputError, Actual, self.bad_cmdresult)

    def test_output_good(self):
        cmdresult = FakeCmdResult('docker', 0, "STDOUT", "STDERR", 123)

        cmdresult.stderr = "panic: runtime error: slice bounds out of range"
        str(self.output.OutputGood(cmdresult, False,
                                   ['crash_check', 'error_check']))
        self.assertRaises(self.output.xceptions.DockerOutputError,
                          self.output.OutputGood, cmdresult)

        cmdresult.stderr = ""
        cmdresult.stdout = "Usage: docker [OPTIONS] COMMAND [arg...]"
        self.assertRaises(self.output.xceptions.DockerOutputError,
                          self.output.OutputGood, cmdresult)


class DockerVersionTest(unittest.TestCase):

    def setUp(self):
        import output
        self.output = output

    def test_client(self):
        version_string = ("Client version: 0.9.0\n"
                          "Go version (client): go1.2\n"
                          "Git commit (client): 2b3fdf2/0.9.0\n"
                          "Server version: 0.8.0\n"
                          "Git commit (server): 2b3fdf2/0.9.0\n"
                          "Go version (server): go1.2\n"
                          "Last stable version: 0.9.0\n")
        docker_version = self.output.DockerVersion(version_string)
        self.assertEqual(docker_version.client, '0.9.0')
        self.assertEqual(docker_version.server, '0.8.0')

    def test_client_new(self):
        version_string = (
            "Client:\n"
            " Version:      1.8.2\n"
            "\n"
            " Built:        \n"
            "\n"
            "\n"
            "Server:\n"
            "\n"
            " API version:  1.20\n"
            " Version:      1.8.2\n"
            "\n")
        docker_version = self.output.DockerVersion(version_string)
        self.assertEqual(docker_version.client, '1.8.2')
        self.assertEqual(docker_version.server, '1.8.2')

    def test_client_info_new(self):
        version_string = (
            "Client:\n"
            " Go version:   go1.4.2\n"
            " OS/Arch:      linux/amd64:special\n"
            "\n"
            "Server:\n"
            " Go version:   go1.2.3\n"
            " Built:        \n")
        docker_version = self.output.DockerVersion(version_string)
        self.assertEqual(docker_version.client_info('OS/Arch'),
                         'linux/amd64:special')
        self.assertEqual(docker_version.server_info('bUIlt'),
                         '')
        self.assertEqual(docker_version.client_info('Go verSion  '),
                         'go1.4.2')
        self.assertEqual(docker_version.server_info('Go verSion  '),
                         'go1.2.3')


class ColumnRangesTest(unittest.TestCase):

    table = ('CONTAINER ID        IMAGE               COMMAND             '
             'CREATED             STATUS              PORTS               '
             'NAMES')

    def setUp(self):
        from output import ColumnRanges
        self.ColumnRanges = ColumnRanges

    def test_init(self):
        self.assertRaises(ValueError, self.ColumnRanges, '')
        self.assertRaises(ValueError, self.ColumnRanges, " ")
        self.assertRaises(ValueError, self.ColumnRanges, "\0\0")
        self.assertRaises(ValueError, self.ColumnRanges, """\n\n\n\n\n""")

    def test_getitem(self):
        tc = self.ColumnRanges(self.table)
        self.assertEqual(len(tc), 7)
        for c in ('CONTAINER ID', 'IMAGE', (0, 20), 'COMMAND', (20, 40),
                  'CREATED', 'STATUS', (60, 80), 'PORTS', 'NAMES'):
            self.assertTrue(c in tc)
        for n in xrange(1, 120):
            self.assertTrue(n not in tc)
            self.assertFalse(n in tc)

    def test_offset(self):
        tc = self.ColumnRanges(self.table)
        self.assertEqual(tc.offset(7), 'CONTAINER ID')
        self.assertEqual(tc.offset(20), 'IMAGE')
        self.assertEqual(tc.offset(len(self.table)), 'NAMES')
        self.assertEqual(tc.offset(99999), 'NAMES')
        self.assertEqual(tc.offset(-99999), 'NAMES')
        self.assertEqual(tc.offset(None), 'NAMES')


class TextTableTest(unittest.TestCase):

    table = ('  one   two   three  \n'  # header
             'foo   bar   \n'
             '1     2     3   4  \n\n'
             '     a     b     c\n\n')

    expected = [
        {'one': 'foo', 'two': 'bar', 'three': None},
        {'one': '1', 'two': '2', 'three': '3   4'},
        {'one': None, 'two': None, 'three': None},
        {'one': 'a', 'two': 'b', 'three': 'c'},
    ]

    def setUp(self):
        from output import TextTable
        self.TT = TextTable

    def test_single_init(self):
        lines = self.table.splitlines()
        tt = self.TT(lines[0])
        self.assertEqual(len(tt), 0)

    def test_multi_init(self):
        tt = self.TT(self.table)
        self.assertEqual(len(tt), len(self.expected))

    def test_multi_init_dupe(self):
        tt = self.TT(self.table)
        tt.allow_duplicate = True
        tt.append({'one': None, 'two': None, 'three': None})
        self.assertEqual(len(tt), len(self.expected) + 1)

    def test_compare(self):
        tt = self.TT(self.table)
        self.assertEqual(tt, self.expected)

    def test_images(self):
        tt = self.TT("""REPOSITORY                    TAG                 IMAGE ID                                                           CREATED             VIRTUAL SIZE
192.168.122.245:5000/fedora   32                  0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404   5 weeks ago         387 MB
fedora                        32                  0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404   5 weeks ago         387 MB
fedora                        rawhide             0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404   5 weeks ago         387 MB
192.168.122.245:5000/fedora   latest              58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9   5 weeks ago         385.5 MB
fedora                        20                  58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9   5 weeks ago         385.5 MB
fedora                        heisenbug           58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9   5 weeks ago         385.5 MB
fedora                        latest              58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9   5 weeks ago         385.5 MB
""")
        self.assertEqual(tt.columnranges.values(),
                         ['REPOSITORY', 'TAG', 'IMAGE ID', 'CREATED',
                          'VIRTUAL SIZE'])
        sr = tt.search('IMAGE ID', ('58394af373423902a1b97f209a31e3777932'
                                    'd9321ef10e64feaaa7b4df609cf9'))
        self.assertEqual(len(sr), 4)
        sr = tt.find('TAG', 'rawhide')
        self.assertEqual(sr['REPOSITORY'], 'fedora')

    def test_containers(self):
        tt = self.TT("""CONTAINER ID                                                       IMAGE               COMMAND                                                                                                                   CREATED              STATUS                          PORTS               NAMES               SIZE
96e1db5c0fd559d7ad4c472425c8b5f1f5b8c3b5952cc1fdc3eee846f6b33fea   fedora:20           bash -c 'echo 'this is a really really really really super big really really really really long command' > /tmp/foobar'   About a minute ago   Exited (0) About a minute ago                       dreamy_brattain     166 B
05a75d9d2d6908c414a479c100fe19ba63b582131b0a276f4df37ead82effcb1   fedora:20           "bash -c 'echo 'line one
line two
line three
' > /tmp/foobar'"   9 minutes ago       Exited (0) 9 minutes ago                       agitated_galileo    107 B""")

        sr = tt.search('IMAGE', 'fedora:20')
        self.assertEqual(len(sr), 2)
        x = sr[0]
        self.assertEqual(x['CONTAINER ID'],
                         ('96e1db5c0fd559d7ad4c472425c8b5f'
                          '1f5b8c3b5952cc1fdc3eee846f6b33f'
                          'ea'))
        self.assertEqual(x['COMMAND'], ("bash -c 'echo 'this is a "
                                        "really really really really "
                                        "super big really really really "
                                        "really long command' > /tmp/foobar'"))
        self.assertEqual(x['CREATED'], 'About a minute ago')
        self.assertEqual(x['STATUS'], 'Exited (0) About a minute ago')
        self.assertEqual(x['PORTS'], None)
        self.assertEqual(x['NAMES'], 'dreamy_brattain')
        self.assertEqual(x['SIZE'], '166 B')
        # The last item with newlines isn't parsed properly, hence no unittest


class WaitForOutput(unittest.TestCase):

    def setUp(self):
        self.old_time = time.time
        self.old_sleep = time.sleep
        setattr(mock('time'), 'time', self.get_time)
        setattr(mock('time'), 'sleep', self.sleep)
        import output
        self.output = output
        self.gtime = self.timegen()

    def tearDown(self):
        setattr(mock('time'), 'time', self.old_time)
        setattr(mock('time'), 'sleep', self.old_sleep)

    def test_wait_for_output(self):
        pattern = r"exp_out"
        ogen = self.outgenerator(2, pattern)
        out = lambda: ogen.next()
        self.assertEqual(self.output.wait_for_output(out, pattern, 8, 1),
                         True)

        t = time.time()
        ogen = self.outgenerator(10, pattern)
        out = lambda: ogen.next()
        self.assertEqual(self.output.wait_for_output(out, pattern, 2, 1),
                         False)
        e = time.time()
        self.assertGreater(t + 7, e,
                           "Waiting for output takes longer time")

    @staticmethod
    def outgenerator(raise_time, expected_out):
        t = time.time()
        raise_t = t + raise_time
        out = ""
        while time.time() < raise_t:
            for _ in xrange(30):
                out += chr(random.randint(32, 100))
            yield out
        out += expected_out
        yield out

        while 1:
            for _ in xrange(30):
                out += chr(random.randint(32, 100))
            yield out

    @staticmethod
    def timegen():
        t = 0
        while 1:
            t += 1
            yield t

    def get_time(self):
        return self.gtime.next()

    @staticmethod
    def sleep(_):
        pass


class TestDtFromIso(unittest.TestCase):

    def setUp(self):
        import output
        self.utc = output.DockerTime.UTC()
        self.dockertime = output.DockerTime
        from datetime import datetime
        self.datetime = datetime

    def test_zero(self):
        epoch_str = "0001-01-01T00:00:00Z"
        epoch_dt = self.dockertime(epoch_str)
        expected = self.datetime(year=1, month=1, day=1,
                                 hour=0, minute=0, second=0,
                                 tzinfo=self.utc)
        self.assertEqual(epoch_dt, expected)

    def test_zero_point_zero(self):
        import datetime
        epoch_str = "0001-01-01T00:00:00.0Z"
        epoch_dt = self.dockertime(epoch_str)
        expected = self.dockertime.UTC.EPOCH
        self.assertEqual(epoch_dt, expected)

    def test_sometime(self):
        import datetime
        epoch_str = "2015-03-02T17:04:20Z"
        epoch_dt = self.dockertime(epoch_str)
        expected = self.datetime(year=2015, month=3, day=2,
                                 hour=17, minute=4, second=20,
                                 tzinfo=self.utc)
        self.assertEqual(epoch_dt, expected)

    def test_sometime_point(self):
        import datetime
        epoch_str = "2015-03-02T17:04:20.569502125Z"
        epoch_dt = self.dockertime(epoch_str)
        expected = self.datetime(year=2015, month=3, day=2,
                                 hour=17, minute=4, second=20,
                                 microsecond=569502, tzinfo=self.utc)
        self.assertEqual(epoch_dt, expected)

    def test_sometime_point_less(self):
        import datetime
        epoch_str = "2015-03-02T17:04:20.569Z"
        epoch_dt = self.dockertime(epoch_str)
        expected = self.datetime(year=2015, month=3, day=2,
                                 hour=17, minute=4, second=20,
                                 microsecond=569000, tzinfo=self.utc)
        self.assertEqual(epoch_dt, expected)

    def test_sometime_point_more(self):
        import datetime
        epoch_str = "2015-03-02T17:04:20.12345678901234567890Z"
        epoch_dt = self.dockertime(epoch_str)
        expected = self.datetime(year=2015, month=3, day=2,
                                 hour=17, minute=4, second=20,
                                 microsecond=123456, tzinfo=self.utc)
        self.assertEqual(epoch_dt, expected)

    def test_is_undefined(self):
        dt = self.dockertime("0001-01-01T00:00:00Z")
        self.assertTrue(dt.is_undefined())

    def test_isoformat(self):
        # Have to normalize representation first for comparison
        dt = self.dockertime("2015-03-02T17:04:20.12345678901234567890Z")
        normalized_isoformat = dt.isoformat()
        dt = self.dockertime(normalized_isoformat)
        test_isoformat = dt.isoformat()
        self.assertEqual(normalized_isoformat, test_isoformat)

    def test_offset_point_some(self):
        import datetime
        isostr = "2015-03-02T17:04:20.569+12:34"
        dt = self.dockertime(isostr)
        tz = self.dockertime.UTCOffset("+12:34")
        expected = datetime.datetime(year=2015, month=3, day=2,
                                     hour=17, minute=4, second=20,
                                     microsecond=569000, tzinfo=tz)
        self.assertEqual(dt, expected)

    def test_in_junk(self):
        import datetime
        isostr = "  2015-03-02T17:04:20.569+12:34 ahhhh! 2015-03-02T 17:04:20"
        dt = self.dockertime(isostr)
        tz = self.dockertime.UTCOffset("+12:34")
        expected = datetime.datetime(year=2015, month=3, day=2,
                                     hour=17, minute=4, second=20,
                                     microsecond=569000, tzinfo=tz)
        self.assertEqual(dt, expected)

    def test_in_other_junk(self):
        import datetime
        isostr = "  ahhhh!2015-03-02T17:04:20z2015-03-02 17:04:20"
        dt = self.dockertime(isostr)
        tz = self.dockertime.UTC()
        expected = datetime.datetime(year=2015, month=3, day=2,
                                     hour=17, minute=4, second=20,
                                     tzinfo=tz)
        self.assertEqual(dt, expected)

    def test_unparsable(self):
        self.assertRaises(ValueError, self.dockertime, "2015-03-02 17:04:20z")

if __name__ == '__main__':
    unittest.main()
