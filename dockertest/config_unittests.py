#!/usr/bin/env python

import unittest, tempfile, shutil, os, sys

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
        # Verify these all are convereted to lower-case automatically
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
        bar.set("testoptionx", "True") # should convert to boolean
        bar.write(self.cfgfile)

    def test_config_defaults(self):
        foobar = self.config.Config()
        self.assertEqual(len(foobar), 2)
        testsection = foobar['TestSection']
        self.assertEqual(len(testsection), 5)
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
        self.assertEqual(len(testsection), 5)
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

if __name__ == '__main__':
    unittest.main()
