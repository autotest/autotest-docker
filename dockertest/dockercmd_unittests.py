#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403
# There is magic requiring attributes defined outside the __init__
# pylint: disable=W0201

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


class FakePopen(object):

    """needed for testing AsyncDockerCmd"""
    pid = -1

    def poll(self):
        return True


class FakeCmdResult(object):    # pylint: disable=R0903

    """ Just pack whatever args received into attributes """
    duration = 123
    stdout = "STDOUT"
    stderr = "STDERR"
    exit_status = 0

    def __init__(self, *args, **dargs):
        self.sp = FakePopen()
        for key, val in dargs.items():
            setattr(self, key, val)

    def __str__(self):
        return self.command
    # needed for testing AsyncDockerCmd

    def get_stdout(self):
        return "STDOUT"

    def get_stderr(self):
        return "STDERR"

    def wait_for(self, timeout):
        self.duration = timeout
        return self

    @property
    def result(self):
        return self


def run(command, *args, **dargs):
    """ Don't actually run anything! """
    result = FakeCmdResult(command=command, args=args, dargs=dargs)
    if 'unittest_fail' in command:
        result.exit_status = 1
        if not dargs['ignore_status']:
            exc = Exception()   # CmdError is mocked, create suitable Exc here
            exc.command = command
            exc.result_obj = result
            raise exc
    else:
        result.exit_status = 0
    return result


# Mock module and mock function run in one command
setattr(mock('autotest.client.utils'), 'run', run)
# Similar enough to run
setattr(mock('autotest.client.utils'), 'AsyncJob', run)
setattr(mock('autotest.client.utils'), 'CmdResult', FakeCmdResult)
# Mock module and class in one stroke
setattr(mock('autotest.client.test'), 'test', object)
# Mock module and exception class in one stroke
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)
setattr(mock('autotest.client.shared.version'), 'get_version',
        lambda: version.AUTOTESTVERSION)
# Need all three for Subtest class
mock('autotest.client.shared.base_job')
mock('autotest.client.shared.job')
mock('autotest.client.shared.utils')
mock('autotest.client.job')

import version


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
        cfgsect.set('__example__', '')
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

            def __init__(fake_self, *_args, **_dargs):  # pylint: disable=E0213
                # Unittest magic pylint: disable=E1003
                super(FakeSubtestException, self).__init__()
                # Unittest magic pylint: enable=E1003

        class FakeSubtest(self.subtest.Subtest):
            version = "1.2.3"
            config_section = self.config_section
            iteration = 1
            iterations = 1

            def __init__(fake_self, *_args, **_dargs):  # pylint: disable=E0213
                config_parser = self.config.Config()
                fake_self.config = config_parser.get(self.config_section)
                for symbol in ('execute', 'setup', 'initialize', 'run_once',
                               'postprocess_iteration', 'postprocess',
                               'cleanup', 'failif',):
                    setattr(fake_self, symbol, FakeSubtestException)
                for symbol in ('logdebug', 'loginfo', 'logwarning',
                               'logerror'):
                    setattr(fake_self, symbol, lambda *_a, **_d: None)
        return FakeSubtest()

    def setUp(self):
        import config
        import dockercmd
        import output
        import subtest
        import xceptions
        self.xceptions = xceptions
        self.config = config
        self.dockercmd = dockercmd
        self.output = output
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
        if 'dockertest.config' in sys.modules:  # Running from outer dir
            del sys.modules['dockertest.config']
            del sys.modules['dockertest.dockercmd']
            del sys.modules['dockertest.subtest']
        else:   # Running from this dir
            del sys.modules['config']
            del sys.modules['dockercmd']
            del sys.modules['subtest']


class DockerCmdTestBasic(DockerCmdTestBase):

    defaults = {'docker_path': '/foo/bar', 'docker_options': '--not_exist',
                'docker_timeout': "42.0"}
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

        self.assertRaises(self.dockercmd.DockerTestError,
                          self.dockercmd.DockerCmdBase, "ThisIsNotSubtest",
                          "fake_subcmd")

    def test_dockercmd(self):
        docker_command = self.dockercmd.DockerCmd(self.fake_subtest,
                                                  'fake_subcommand',
                                                  ['fake', 'arg', 'list'],
                                                  1234567)

        expected = ("%s %s fake_subcommand fake arg list"
                    % (self.defaults['docker_path'],
                       self.defaults['docker_options']))
        self.assertTrue(docker_command.command in expected)
        self.assertTrue(expected in str(docker_command))
        self.assertTrue(docker_command.cmdresult is None)
        cmdresult = docker_command.execute()
        self.assertTrue(docker_command.cmdresult is not None)
        self.assertTrue(cmdresult.command in expected)
        # mocked cmdresult has '.dargs' pylint: disable=E1101
        self.assertAlmostEqual(cmdresult.duration, 123)
        # pylint: enable=E1101
        # Verify can change some stuff
        docker_command.timeout = 0
        docker_command.subcmd = ''
        docker_command.subargs = []
        self.assertTrue(docker_command.cmdresult is not None)
        cmdresult = docker_command.execute()
        self.assertTrue(docker_command.cmdresult is not None)
        expected = ("%s %s" % (self.defaults['docker_path'],
                               self.defaults['docker_options']))
        self.assertEqual(cmdresult.command, expected)
        # mocked cmdresult has '.dargs' pylint: disable=E1101
        self.assertAlmostEqual(cmdresult.duration, 123)
        # pylint: enable=E1101

    def test_no_fail_docker_cmd(self):
        docker_command = self.dockercmd.DockerCmd(self.fake_subtest,
                                                  'fake_subcommand')
        self.assertTrue(self.output.mustpass(docker_command.execute()))

        docker_command = self.dockercmd.DockerCmd(self.fake_subtest,
                                                  'unittest_fail')
        self.assertRaises(self.xceptions.DockerExecError,
                          self.output.mustpass, docker_command.execute())

    def test_must_fail_docker_cmd(self):
        docker_command = self.dockercmd.DockerCmd(self.fake_subtest,
                                                  'fake_subcommand')
        self.assertRaises(self.xceptions.DockerExecError,
                          self.output.mustfail, docker_command.execute())

        docker_command = self.dockercmd.DockerCmd(self.fake_subtest,
                                                  'unittest_fail')
        self.assertTrue(self.output.mustfail(docker_command.execute()))


class AsyncDockerCmd(DockerCmdTestBase):
    defaults = {'docker_path': '/foo/bar', 'docker_options': '--not_exist',
                'docker_timeout': "42.0"}
    customs = {}
    config_section = "Foo/Bar/Baz"

    def test_basic_workflow(self):
        docker_cmd = self.dockercmd.AsyncDockerCmd(self.fake_subtest,
                                                   'fake_subcommand',
                                                   timeout=123)

        # Raise error when command not yet executed
        self.assertRaises(self.dockercmd.DockerTestError, docker_cmd.wait)
        for prop in ('done', 'process_id'):
            self.assertRaises(self.dockercmd.DockerTestError,
                              getattr, docker_cmd, prop)

        cmdresult = docker_cmd.execute()
        self.assertTrue(isinstance(cmdresult, FakeCmdResult))
        self.assertEqual(docker_cmd.wait(123).duration, 123)
        self.assertTrue(docker_cmd.done)
        self.assertEqual(docker_cmd.stdout, "STDOUT")
        self.assertEqual(docker_cmd.stderr, "STDERR")
        self.assertEqual(docker_cmd.process_id, -1)


if __name__ == '__main__':
    unittest.main()
