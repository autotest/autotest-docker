#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import unittest, sys, types, tempfile, os, shutil

class ContainersTestBase(unittest.TestCase):

    def setUp(self):
        import containers
        self.containers = containers
        self.DC = self.containers.DockerContainer
        self.DCB = self.containers.DockerContainersBase

    def tearDown(self):
        del self.containers

class DockerContainersTest(ContainersTestBase):

    def test_init_defaults(self):
        foo = object()
        dc = self.DC(foo, r"/bin/echo -ne 'hello world\n'")
        self.assertEqual(dc.image_name, foo)
        self.assertEqual(dc.command, r"/bin/echo -ne 'hello world\n'")
        self.assertEqual(dc.long_id, None)
        self.assertEqual(dc.created, None)
        self.assertEqual(dc.status, None)
        self.assertEqual(dc.size, None)

    def test_init_setup(self):
        foo = object()
        dc = self.DC(foo, r"/bin/echo -ne 'hello world\n'", "foobar")
        dc.long_id = "1234"
        dc.created = "Yesterday"
        dc.status = "Up 42 hours"
        dc.size = "1 Petabyte"
        self.assertEqual(dc.image_name, foo)
        self.assertEqual(dc.command, r"/bin/echo -ne 'hello world\n'")
        self.assertEqual(dc.long_id, "1234")
        self.assertEqual(dc.created, "Yesterday")
        self.assertEqual(dc.status, "Up 42 hours")
        self.assertEqual(dc.size, "1 Petabyte")

    def test_eq_ne(self):
        foo = {'one':1, 'two':2, 'three':3}
        bar = {'three':3, 'two':2, 'one':1}
        baz = foo.copy()
        baz.update(bar)
        dc1 = self.DC(foo, r"/bin/echo -ne 'hello world\n'", "foobar")
        dc2 = self.DC(bar, r"/bin/echo -ne 'hello world\n'", "foobar")
        dc3 = self.DC(baz, r"/bin/echo -ne 'hello world\n'", "foobar")
        self.assertEqual(dc1, dc1)
        self.assertEqual(dc2, dc2)
        self.assertEqual(dc1, dc2)
        self.assertEqual(dc3, dc3)
        self.assertNotEqual(dc3, dc1)
        self.assertNotEqual(dc3, dc2)

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
    command = str(command)
    return FakeCmdResult(command=command.strip(),
                         stdout=r"""
CONTAINER ID                                                       IMAGE                             COMMAND                                            CREATED             STATUS              PORTS                                            NAMES               SIZE
ac8c9fa367f96e10cbfc7927dd4048d7db3e6d240d201019c5d4359795e3bcbe   busybox:latest                    "/bin/sh -c echo -ne "hello world\n"; sleep 10m"   5 minutes ago       Up 79 seconds                                                        cocky_albattani     77 B
ef0fe72271778aefcb5cf6015f30067fbe01f05996a123037f65db0b82795915   busybox:latest                    "/bin/sh -c echo -ne "world hello\n"; sleep 10m"   82 seconds ago      Up 61 seconds       4.3.2.1:4321->1234/bar, 1.2.3.4:1234->4321/foo   berserk_bohr        55 B
849915d551d80edce7698de91852c06bbbb7a67fe0968a3c0c246e6f25f81017   busybox:latest                    "/bin/sh -c echo -ne "hello world\n"; sleep 10m"   28 seconds ago      Up 16 seconds       1.2.3.4:1234->4321/foo, 0.0.0.0:5678->8765/tcp   berserk_bohr        77 B
c0c35064e4d2bdcf86e6fd83e0de2e599473c12a6599415a9a021bdf382a3589   busybox:latest                    "/bin/sh -c echo -ne "hello world\n""              5 minutes ago       Exit 0                                                               lonely_poincare     77 B
3723b1b0abd7be84316ce7824e68cb7af090416296c539a28d169495f44a6319   busybox:latest                    "/bin/bash -c echo -ne "hello world\n""            6 minutes ago       Exit 1                                                               clever_brattain     77 B
abf8c40b19e353ff1f67e3a26a967c14944b07b8f5aceb752f781ffca285a2a9   10.16.71.105:5000/fedora:latest   /bin/bash                                          22 hours ago        Exit 0                                                               suspicious_pare     77 B
e1820ef428b51a95c963353cc4ce6b57ea0a20c44537a8336792510713dfe524   10.16.71.105:5000/fedora:latest   /bin/bash                                          22 hours ago        Exit 0                                                               thirsty_mccarthy    77 B
""",
                        stderr='',
                        exit_status=0,
                        duration=42)

# Mock module and mock function run in one line
setattr(mock('autotest.client.utils'), 'run', run)
setattr(mock('autotest.client.utils'), 'CmdResult', FakeCmdResult)
# Mock module and exception class in one line
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.test'), 'test', object)
mock('autotest.client.shared.base_job')
mock('autotest.client.shared.job')
mock('autotest.client.job')
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)

class DockerContainersTestBase(ContainersTestBase):

    defaults = {'docker_path': '/foo/bar', 'docker_options': '--not_exist',
                'docker_timeout': 60.0, 'config_version': '0.3.1'}
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
                    setattr(fake_self, symbol, lambda *a, **d: None)
        return FakeSubtest()

    def setUp(self):
        super(DockerContainersTestBase, self).setUp()
        import config
        import subtest
        self.config = config
        self.subtest = subtest
        self.config.CONFIGDEFAULT = tempfile.mkdtemp(self.__class__.__name__)
        self.config.CONFIGCUSTOMS = tempfile.mkdtemp(self.__class__.__name__)
        self._setup_defaults()
        self._setup_customs()
        self.fake_subtest = self._make_fake_subtest()

    def tearDown(self):
        super(DockerContainersTestBase, self).tearDown()
        shutil.rmtree(self.config.CONFIGDEFAULT, ignore_errors=True)
        shutil.rmtree(self.config.CONFIGCUSTOMS, ignore_errors=True)
        self.assertFalse(os.path.isdir(self.config.CONFIGDEFAULT))
        self.assertFalse(os.path.isdir(self.config.CONFIGCUSTOMS))
        del self.config
        del self.subtest

class DockerContainersTest(DockerContainersTestBase):

    def test_defaults(self):
        dcc = self.containers.DockerContainersCLI(self.fake_subtest)
        cl = dcc.list_containers()
        self.assertEqual(len(cl), 7)

    def test_noports(self):
        dcc = self.containers.DockerContainersCLI(self.fake_subtest)
        short_id = "ac8c9fa367f9"
        cl = [c for c in dcc.list_containers() if c.cmp_id(short_id)]
        self.assertEqual(len(cl), 1)
        self.assertEqual(cl[0].ports, "")

    def test_ports(self):
        from networking import ContainerPort
        dcc = self.containers.DockerContainersCLI(self.fake_subtest)
        long_id = ("ef0fe72271778aefcb5cf6015f30067fbe"
                   "01f05996a123037f65db0b82795915")
        cl = [c for c in dcc.list_containers() if c.cmp_id(long_id)]
        self.assertEqual(len(cl), 1)
        ports = []
        for portstr in cl[0].ports.split(','):
            components = ContainerPort.split_to_component(portstr.strip())
            ports.append(ContainerPort(*components))
        self.assertEqual(len(ports), 2)
        p0, p1 = ports
        self.assertEqual(p0.protocol, 'bar')
        self.assertEqual(p1.host_port, 1234)

if __name__ == '__main__':
    unittest.main()
