#!/usr/bin/env python

import unittest, tempfile, shutil, os, sys, types

def mock(mod_path):
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

class FakeCmdResult(object):
    def __init__(self, **dargs):
        for key, val in dargs.items():
            setattr(self, key, val)

def run(command, *args, **dargs):
    command = "%s %s" % (command, " ".join(dargs['args']))
    return FakeCmdResult(command=command.strip(),
                         stdout=args,
                         stderr=dargs,
                         exit_status=len(args),
                         duration=len(dargs))

# Mock module and mock function run in one command
setattr(mock('autotest.client.utils'), 'run', run)
setattr(mock('autotest.client.utils'), 'CmdResult', FakeCmdResult)
setattr(mock('autotest.client.test'), 'test', object)
mock('autotest.client.shared.error')
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

    defaults = {'docker_path':'/foo/bar', 'docker_options':'--not_exist'}
    customs = {}
    config_section = "Foo/Bar/Baz"

    def test_defaults(self):
        docker_command = self.dockercmd.DockerCmd(self.fake_subtest, '')
        self.assertEqual(docker_command.stdin_file, None)
        self.assertEqual(docker_command.verbose, True)
        self.assertEqual(docker_command.timeout, 60 * 60)
        self.assertEqual(docker_command.ignore_status, True)
        expected = ("%s %s" % (self.defaults['docker_path'],
                               self.defaults['docker_options']))
        self.assertEqual(docker_command.command, expected)
        self.assertEqual(docker_command.exit_status, 0)
        self.assertEqual(docker_command.duration, 5)

    def test_props(self):
        docker_command = self.dockercmd.DockerCmd(self.fake_subtest, '')
        self.assertEqual(docker_command.docker_options,
                         self.defaults['docker_options'])
        self.assertEqual(docker_command.docker_command,
                         self.defaults['docker_path'])
        self.assertEqual(docker_command.args,
                         (self.defaults['docker_options'], ''))
        self.assertEqual(docker_command.full_command.strip(),
                         ("%s %s" % (self.defaults['docker_path'],
                                     self.defaults['docker_options'])))

if __name__ == '__main__':
    unittest.main()
