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


class DockerVersionError(IOError):
    """ Dummy exception """
    pass


class DockerValueError(IOError):
    """ Dummy exception """
    pass


# Mock module and exception class in one stroke
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)
setattr(mock('xceptions'), 'DockerVersionError', DockerVersionError)
setattr(mock('xceptions'), 'DockerValueError', DockerValueError)
setattr(mock('dockertest.xceptions'), 'DockerVersionError', DockerVersionError)
setattr(mock('dockertest.xceptions'), 'DockerValueError', DockerValueError)


class VersionTestBase(unittest.TestCase):

    def setUp(self):
        import version
        self.version = version


class VersionTest(VersionTestBase):

    def test_types(self):
        for thing in (self.version.MAJOR, self.version.MINOR,
                      self.version.REVIS):
            self.assertTrue(isinstance(thing, int))
        self.assertTrue(isinstance(self.version.FMTSTRING, (str, unicode)))
        self.assertTrue(isinstance(self.version.STRING, (str, unicode)))

    def test_compare_str(self):
        major = self.version.MAJOR
        minor = self.version.MINOR
        revis = self.version.REVIS
        lstr = self.version.STRING
        rstr = (self.version.FMTSTRING % (major, minor, revis + 1))
        self.assertEqual(self.version.compare(lstr, rstr), 0)  # equal
        rstr = (self.version.FMTSTRING % (major, minor + 1, revis + 1))
        self.assertEqual(self.version.compare(lstr, rstr), -1)  # less
        lstr = (self.version.FMTSTRING % (major, minor + 10, revis))
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
        # Incorrect value
        self.assertRaises(ValueError, self.version.compare, None, None)

    def test_str2int(self):
        self.assertEqual(self.version.str2int("3.1.5"), 196869)
        self.assertRaises(AssertionError, self.version.str2int, "256.1.5")
        self.assertRaises(AssertionError, self.version.str2int, "1.1.5.1")

    def test_int2str(self):
        self.assertEqual(self.version.int2str(123456), "1.226.64")

    def test_check_version(self):
        def increment(*_args, **_kwargs):
            self.__counter += 1

        _version = self.version.STRING
        self.version.STRING = '1.2.3'
        config = {'config_version': '1.2.3'}    # Correct version
        self.assertEqual(self.version.check_version(config), None)

        config['config_version'] = '2.0.0'      # Incorrect version
        self.assertRaises(DockerVersionError,
                          self.version.check_version, config)
        self.version.STRING = _version

        config['config_version'] = ""         # Bad type
        self.assertRaises(DockerVersionError,
                          self.version.check_version, config)

        config['config_version'] = None         # Incorrect type
        self.assertRaises(DockerValueError,
                          self.version.check_version, config)

        config['config_version'] = '@!NOVERSIONCHECK!@'
        self.__counter = 0
        _logging_mock = mock('logging')     # Don't spam the output
        _logging_orig = getattr(_logging_mock, 'warning')
        setattr(_logging_mock, 'warning', increment)
        self.assertEqual(self.version.check_version(config), None)
        setattr(_logging_mock, 'warning', _logging_orig)    # cleanup
        self.assertEqual(self.__counter, 1, "logging.warn was not used while "
                         "checking version with NOVERSIONCHECK")

if __name__ == '__main__':
    unittest.main()
