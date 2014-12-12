#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import os
import shutil
import sys
import tempfile
import types
import unittest


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


class DockerKeyError(Exception):

    """ Fake class for errors """
    pass


# Mock module and exception class in one stroke
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)
setattr(mock('dockertest.xceptions'), 'DockerKeyError', DockerKeyError)
setattr(mock('dockertest.xceptions'), 'DockerConfigError', DockerKeyError)
setattr(mock('dockertest.xceptions'), 'DockerIOError', DockerKeyError)
setattr(mock('xceptions'), 'DockerKeyError', DockerKeyError)
setattr(mock('xceptions'), 'DockerConfigError', DockerKeyError)
setattr(mock('xceptions'), 'DockerIOError', DockerKeyError)


class ConfigTestBase(unittest.TestCase):

    def setUp(self):
        import config
        self.config = config
        self.config.CONFIGDEFAULT = tempfile.mkdtemp(self.__class__.__name__)
        self.config.CONFIGCUSTOMS = tempfile.mkdtemp(self.__class__.__name__)

    def tearDown(self):
        shutil.rmtree(self.config.CONFIGDEFAULT, ignore_errors=True)
        shutil.rmtree(self.config.CONFIGCUSTOMS, ignore_errors=True)
        self.assertFalse(os.path.isdir(self.config.CONFIGDEFAULT))
        self.assertFalse(os.path.isdir(self.config.CONFIGCUSTOMS))
        if 'dockertest.config' in sys.modules:  # running from outer directory
            del sys.modules['dockertest.config']
        else:       # Running from this directory
            del sys.modules['config']


class TestConfigSection(ConfigTestBase):

    def test_write_read(self):
        osfd, filename = tempfile.mkstemp(suffix='.ini',
                                          dir=self.config.CONFIGDEFAULT)
        os.close(osfd)
        testfile = open(filename, 'wb')
        foo = self.config.ConfigSection(None, 'TestSection')
        foo.set('TestOption', 'TestValue')
        foo.write(testfile)
        testfile.close()
        bar = self.config.ConfigSection(None, 'TestSection')
        self.assertEqual(bar.read(testfile.name), [testfile.name])
        # Note the case-conversion
        self.assertEqual(bar.get('testoption'), 'TestValue')

        self.assertEqual(len(foo.sections()), 1)
        self.assertTrue(foo.has_section("TestSection"))
        self.assertTrue(foo.has_option("testoption"))

        foo.remove_option("testoption")
        self.assertFalse(foo.has_option("testoption"))


class TestConfigDict(ConfigTestBase):

    def setUp(self):
        super(TestConfigDict, self).setUp()
        osfd, filename = tempfile.mkstemp(suffix='.ini',
                                          dir=self.config.CONFIGDEFAULT)
        os.close(osfd)
        self.testfile = open(filename, 'wb')
        # ConfigDict forbids writing
        foobar = self.config.ConfigSection(None, 'TestSection')
        foobar.set('TEStoptionb', True)
        foobar.set('TestOPTiOni', 2)
        foobar.set('TestoPtionF', 3.14)
        foobar.set('TeSToptionS', "foobarbaz")
        foobar.write(self.testfile)
        self.testfile.close()

    def test_config_dict_pruned(self):
        foobar = self.config.ConfigDict('NotExist')
        foobar.read(open(self.testfile.name, 'rb'))
        self.assertEqual(len(foobar), 0)

    def test_config_dict_read(self):
        foobar = self.config.ConfigDict('TestSection')
        foobar.read(open(self.testfile.name, 'rb'))
        self.assertEqual(len(foobar), 4)

    def test_config_dict_convert(self):
        foobar = self.config.ConfigDict('TestSection')
        foobar.read(open(self.testfile.name, 'rb'))
        self.assertEqual(foobar['testoptions'], "foobarbaz")
        self.assertAlmostEqual(foobar['testoptionf'], 3.14)
        self.assertEqual(foobar['testoptioni'], 2)
        self.assertEqual(foobar['testoptionb'], True)

    def test_basic_functionality(self):
        foobar = self.config.ConfigDict('TestSection')
        self.assertRaises(DockerKeyError, foobar.__getitem__, 'aaa')
        foobar['aaa'] = 'AAA'
        self.assertEqual(foobar['aaa'], "AAA")
        del(foobar['aaa'])


class TestConfig(ConfigTestBase):

    def setUp(self):
        # Changes CONFIGDEFAULT
        super(TestConfig, self).setUp()
        osfd, filename = tempfile.mkstemp(suffix='.ini',
                                          dir=self.config.CONFIGDEFAULT)
        os.close(osfd)
        self.config.DEFAULTSFILE = filename
        self.deffile = open(filename, 'wb')
        # ConfigSection will open again
        self.deffile.close()
        # ConfigDict forbids writing
        foo = self.config.ConfigSection(None, 'DEFAULTS')
        # Verify these all are converted to lower-case automatically
        foo.set('tEsTOPTioNi', 2)  # non-string values should also convert
        foo.set('TesToPTIONf', 3.14)
        foo.set('testoptionS', "foobarbaz")
        foo.write(self.deffile)
        # Set up separate test config file
        osfd, filename = tempfile.mkstemp(suffix='.ini',
                                          dir=self.config.CONFIGDEFAULT)
        os.close(osfd)
        # in case a test needs it
        self.cfgfile = open(filename, 'wb')
        # ConfigSection will open again
        self.cfgfile.close()
        # ConfigDict forbids writing
        bar = self.config.ConfigSection(None, 'TestSection')
        bar.set('TestOptionB', False)
        bar.set('TesTopTIONs', "baz!")
        bar.set("testoptionx", "True")  # should convert to boolean
        bar.write(self.cfgfile)

    def test_config_defaults(self):
        foobar = self.config.Config()
        self.assertEqual(len(foobar), 2)
        testsection = foobar['TestSection']
        self.assertEqual(len(testsection), 6)
        self.assertEqual(testsection['testoptioni'], 2)
        self.assertEqual(testsection['testoptionb'], False)
        self.assertAlmostEqual(testsection['testoptionf'], 3.14)
        self.assertEqual(testsection['testoptions'], "baz!")
        self.assertEqual(testsection['testoptionx'], True)

    def test_cached_copy(self):
        foo = self.config.Config()
        bar = self.config.Config()
        self.assertNotEqual(id(foo), id(bar))

    def test_multi_sections(self):
        osfd, filename = tempfile.mkstemp(suffix='.ini',
                                          dir=self.config.CONFIGDEFAULT)
        os.close(osfd)
        cfgfile = open(filename, 'wb')
        foo = self.config.ConfigSection(None, 'AnotherTestSection')
        bar = self.config.ConfigSection(None, 'YetAnotherTestSection')
        foo.set('TestOptionB', True)
        bar.set('tEstOpTIonx', "false")
        foo.write(cfgfile)
        bar.merge_write(cfgfile)
        # ConfigSection opens copy, verify closing this file after write
        cfgfile.close()
        config = self.config.Config()
        self.assertEqual(len(config), 4)

        testsection = config['TestSection']
        self.assertEqual(len(testsection), 6)
        self.assertEqual(testsection['testoptioni'], 2)
        self.assertEqual(testsection['testoptionb'], False)
        self.assertAlmostEqual(testsection['testoptionf'], 3.14)
        self.assertEqual(testsection['testoptions'], "baz!")
        self.assertEqual(testsection['testoptionx'], True)

        atestsection = config['AnotherTestSection']
        self.assertEqual(atestsection['testoptioni'], 2)  # default
        self.assertEqual(atestsection['testoptionb'], True)  # overridden
        self.assertAlmostEqual(atestsection['testoptionf'], 3.14)  # default
        self.assertEqual(atestsection['testoptions'], "foobarbaz")  # default

        yatestsection = config['YetAnotherTestSection']
        self.assertEqual(yatestsection['testoptioni'], 2)  # default
        self.assertAlmostEqual(yatestsection['testoptionf'], 3.14)  # default
        self.assertEqual(atestsection['testoptions'], "foobarbaz")  # default
        self.assertEqual(yatestsection['testoptionx'], False)  # overridden

    def test_warn(self):
        # Global DEFAULTS defines tEsTOPTioNi, TesToPTIONf, testoptionS

        # This example should get discarded
        dfl = self.config.ConfigSection(None, 'DEFAULTS')
        dfl.set('__example__', 'testoptions')  # should be discarded
        dfl.merge_write(self.deffile)

        # defaults testsection defines TestOptionB, overrides TesTopTIONs
        #                  and defines testoptionx

        foo = self.config.ConfigSection(None, 'TestSection')
        foo.set('__example__', 'tEsTOPTioNi,  TestOptionB, testoptionx')
        # require override on inherited tEsTOPTioNi from DEFAULTS
        foo.set('testoptionb', 'FAIL!')  # modified from DEFAULTS
        foo.set('testoptionx', 'FAIL!')  # redefined here
        foo.remove_option('testoptions') # test DEFAULTS __example__ ignored
        foo.merge_write(self.cfgfile)  # update, don't overwrite

        # Custom config, modifies tEsTOPTioNi,  TestOptionB, testoptionx
        osfd, filename = tempfile.mkstemp(suffix='.ini',  #vvvvvvvvvvvv
                                          dir=self.config.CONFIGCUSTOMS)
        os.close(osfd)
        cfgfile = open(filename, 'wb')
        bar = self.config.ConfigSection(None, 'TestSection')
        bar.set('__example__', 'tEsTOPTioNi,  TestOptionB, testoptionx')
        bar.set('TestOptioni', 'Pass!')
        bar.set('TestOptionB', 'Pass!')
        bar.set('TestOptionX', 'Pass!')
        bar.write(cfgfile)
        cfgfile.close()
        config = self.config.Config()
        self.assertEqual(len(config), 2)
        testsection = config['TestSection']
        self.assertEqual(testsection['__example__'], "")

    def test_warn_default(self):
        # Global DEFAULTS defines tEsTOPTioNi, TesToPTIONf, testoptionS

        # This example should get discarded
        dfl = self.config.ConfigSection(None, 'DEFAULTS')
        dfl.set('__example__', 'testoptioni, testOptionb, TestOptionX')
        dfl.merge_write(self.deffile)

        # defaults testsection defines TestOptionB, overrides TesTopTIONs
        #                  and defines testoptionx

        # Custom config, modifies TestOptionB, testoptionx
        osfd, filename = tempfile.mkstemp(suffix='.ini',  #vvvvvvvvvvvv
                                          dir=self.config.CONFIGCUSTOMS)
        os.close(osfd)
        cfgfile = open(filename, 'wb')
        bar = self.config.ConfigSection(None, 'TestSection')
        bar.set('TestOptionB', 'Pass!')
        bar.set('TestOptionX', 'Pass!')
        bar.write(cfgfile)
        cfgfile.close()
        config = self.config.Config()
        self.assertEqual(len(config), 2)
        testsection = config['TestSection']
        self.assertEqual(testsection['__example__'], "testoptioni")

    def test_warn_custom(self):
        # Global DEFAULTS defines tEsTOPTioNi, TesToPTIONf, testoptionS
        # defaults testsection defines TestOptionB, overrides TesTopTIONs
        #                  and defines testoptionx

        # Custom config, modifies tEsTOPTioNi, TestOptionB, testoptionx
        osfd, filename = tempfile.mkstemp(suffix='.ini',  #vvvvvvvvvvvv
                                          dir=self.config.CONFIGCUSTOMS)
        os.close(osfd)
        cfgfile = open(filename, 'wb')
        bar = self.config.ConfigSection(None, 'TestSection')
        bar.set('__example__', 'tEsTOPTioNi,  TestOptionB, testoptionx')
        bar.set('TestOptioni', 'Pass!')  # differs from default
        bar.set('testoptionb', 'no')  # unchanged from default config
        bar.set('testoptionx', 'yes') # this too
        bar.write(cfgfile)
        cfgfile.close()
        config = self.config.Config()
        self.assertEqual(len(config), 2)
        testsection = config['TestSection']
        # order doesn't matter
        examples= set(self.config.get_as_list(testsection['__example__']))
        expected = set(['testoptionb', 'testoptionx'])
        self.assertEqual(examples, expected)


class TestUtilities(ConfigTestBase):

    def test_nfe_all(self):
        test_dict = {'foo': 0, 'bar': None, 'baz': "      "}
        self.config.none_if_empty(test_dict)
        self.assertEqual(test_dict, {'foo': 0, 'bar': None, 'baz': None})

    def test_nfe_one(self):
        test_dict = {'foo': 0, 'bar': None, 'baz': "      "}
        self.config.none_if_empty(test_dict, 'bar')
        self.assertEqual(test_dict, {'foo': 0, 'bar': None, 'baz': "      "})

    def test_nfe_another(self):
        test_dict = {'foo': 0, 'bar': None, 'baz': "      "}
        self.config.none_if_empty(test_dict, 'baz')
        self.assertEqual(test_dict, {'foo': 0, 'bar': None, 'baz': None})

if __name__ == '__main__':
    unittest.main()
