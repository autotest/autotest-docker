#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import unittest, tempfile, shutil, os, sys, types

# DO NOT allow this function to get loose in the wild!
def mock(mod_path):
    """
    Recursivly inject tree of mocked modules from entire mod_path
    """
    name_list = mod_path.split('.')
    child_name = name_list.pop()
    child_mod = sys.modules.get(mod_path, types.ModuleType(child_name))
    if len(name_list) == 0:  # child_name is left-most basic module
        if not sys.modules.has_key(child_name):
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

# Just pack whatever args received into attributes
class FakeCmdResult(object):
    def __init__(self, **dargs):
        for key, val in dargs.items():
            setattr(self, key, val)

# Don't actually run anything!
def run(command, *args, **dargs):
    return FakeCmdResult(command=command,
                         args=args,
                         dargs=dargs)

# Mock module and mock function run in one command
setattr(mock('autotest.client.utils'), 'run', run)
# Similar enough to run
setattr(mock('autotest.client.utils'), 'AsyncJob', run)
# Mock module and class in one stroke
setattr(mock('autotest.client.test'), 'test', object)
# Mock module and exception class in one stroke
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)
# Need all three for Subtest class
mock('autotest.client.shared.base_job')
mock('autotest.client.shared.job')
mock('autotest.client.job')


class DockerCmdTestBase(unittest.TestCase):

    defaults = {}
    customs = {}
    config_section = "Foo/Bar/Baz"

    def _setup_inifile(self, cfgsection, cfgdir, cfgdict):
        osfd, filename = tempfile.mkstemp(suffix='.ini',
                                          dir=cfgdir)
        os.close(osfd)
        # ConfigSection will open again
        cfgfile = open(filename, 'wb')
        cfgfile.close()
        # ConfigDict forbids writing
        cfgsect = self.config.ConfigSection(None, cfgsection)
        for key, val in cfgdict.items():
            cfgsect.set(key, val)
        cfgsect.write(cfgfile)
        return filename

    def _setup_defaults(self):
        self.config.DEFAULTSFILE = self._setup_inifile('DEFAULTS',
                                   self.config.CONFIGDEFAULT,
                                   self.defaults)

    def _setup_customs(self):
        self._setup_inifile(self.config_section,
                            self.config.CONFIGCUSTOMS,
                            self.customs)

    def _make_fake_subtest(self):
        class FakeSubtestException(Exception):
            def __init__(fake_self, *args, **dargs):
                super(FakeSubtestException, self).__init__()
        class FakeSubtest(self.subtest.Subtest):
            version = "1.2.3"
            config_section = self.config_section
            iteration = 1
            iterations = 1
            def __init__(fake_self, *args, **dargs):
                config_parser = self.config.Config()
                fake_self.config = config_parser.get(self.config_section)
                for symbol in ('execute', 'setup', 'initialize', 'run_once',
                               'postprocess_iteration', 'postprocess',
                               'cleanup', 'failif',):
                    setattr(fake_self, symbol, FakeSubtestException)
                for symbol in ('logdebug', 'loginfo', 'logwarning', 'logerror'):
                    setattr(fake_self, symbol, lambda *a, **d:None)
        return FakeSubtest()

    def setUp(self):
        import config
        import dockercmd
        import subtest
        self.config = config
        self.dockercmd = dockercmd
        self.subtest = subtest
        self.config.CONFIGDEFAULT = tempfile.mkdtemp(self.__class__.__name__)
        self.config.CONFIGCUSTOMS = tempfile.mkdtemp(self.__class__.__name__)
        self._setup_defaults()
        self._setup_customs()
        self.fake_subtest = self._make_fake_subtest()

    def tearDown(self):
        shutil.rmtree(self.config.CONFIGDEFAULT, ignore_errors=True)
        shutil.rmtree(self.config.CONFIGCUSTOMS, ignore_errors=True)
        self.assertFalse(os.path.isdir(self.config.CONFIGDEFAULT))
        self.assertFalse(os.path.isdir(self.config.CONFIGCUSTOMS))
        del self.config
        del self.dockercmd
        del self.subtest
        del sys.modules['config']
        del sys.modules['dockercmd']
        del sys.modules['subtest']


class DockerCmdTestBasic(DockerCmdTestBase):

    defaults = {'docker_path':'/foo/bar', 'docker_options':'--not_exist',
                'docker_timeout':"42.0"}
    customs = {}
    config_section = "Foo/Bar/Baz"

    def test_base(self):
        docker_command = self.dockercmd.DockerCmdBase(self.fake_subtest,
                                                      'fake_subcommand')
        self.assertEqual(docker_command.subtest, self.fake_subtest)
        self.assertEqual(docker_command.subargs, [])
        self.assertEqual(docker_command.docker_options,
                         self.defaults['docker_options'])
        self.assertEqual(docker_command.docker_command,
                         self.defaults['docker_path'])
        self.assertEqual(docker_command.timeout,
                         float(self.defaults['docker_timeout']))
        # Make sure this remains mutable
        docker_command.timeout = 24
        self.assertEqual(docker_command.timeout, 24)
        self.assertRaises(NotImplementedError, docker_command.execute,
                           'not stdin')


    def test_dockercmd(self):
        docker_command = self.dockercmd.DockerCmd(self.fake_subtest,
                                                  'fake_subcommand',
                                                  ['fake', 'arg', 'list'],
                                                  1234567)

        expected = ("%s %s fake_subcommand fake arg list"
                    % (self.defaults['docker_path'],
                       self.defaults['docker_options']))
        self.assertEqual(docker_command.command, expected)
        cmdresult = docker_command.execute()
        self.assertEqual(cmdresult.command, expected)
        self.assertAlmostEqual(cmdresult.dargs['timeout'], 1234567.0)
        # Verify can change some stuff
        docker_command.timeout = 0
        docker_command.subcmd = ''
        docker_command.subargs = []
        cmdresult = docker_command.execute()
        expected = ("%s %s" % (self.defaults['docker_path'],
                               self.defaults['docker_options']))
        self.assertEqual(cmdresult.command, expected)
        self.assertEqual(cmdresult.dargs['timeout'], 0)

if __name__ == '__main__':
    unittest.main()
