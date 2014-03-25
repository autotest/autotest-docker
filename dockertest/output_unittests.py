#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import sys
import types
import unittest


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

# Mock module and exception class in one stroke
mock('autotest.client.utils')
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)


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

    def test_output_map(self):
        class Actual(self.output.OutputGoodBase):
            def good_check(fake_self, output):
                return True
            def actual_check(fake_self, output):
                return fake_self.cmdresult.exit_status == 0
        actual = Actual(self.bad_cmdresult, ignore_error=True)
        self.assertTrue(actual.output_good['good_check'])
        self.assertFalse(actual.output_good['actual_check'])
        actual = Actual(self.good_cmdresult, ignore_error=True)
        self.assertTrue(actual.output_good['good_check'])
        self.assertTrue(actual.output_good['actual_check'])
    # End of classes with fake self pylint: enable=E0213

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
                          "Go version (client): go1.2"
                          "Git commit (client): 2b3fdf2/0.9.0"
                          "Server version: 0.8.0"
                          "Git commit (server): 2b3fdf2/0.9.0"
                          "Go version (server): go1.2"
                          "Last stable version: 0.9.0")
        docker_version = self.output.DockerVersion(version_string)
        self.assertEqual(docker_version.client, '0.9.0')
        self.assertEqual(docker_version.server, '0.8.0')

if __name__ == '__main__':
    unittest.main()
