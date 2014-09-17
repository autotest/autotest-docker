#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import unittest
import sys
import types
import tempfile
import os
import shutil


class ContainersTestBase(unittest.TestCase):

    def setUp(self):
        import containers
        self.containers = containers
        self.DC = self.containers.DockerContainer
        self.DCB = self.containers.DockerContainersBase

    def tearDown(self):
        del self.containers


class DockerContainerTest(ContainersTestBase):

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
        foo = {'one': 1, 'two': 2, 'three': 3}
        bar = {'three': 3, 'two': 2, 'one': 1}
        baz = {'completely': 'different'}
        baz.update(bar)
        dc1 = self.DC(foo, r"/bin/echo -ne 'hello world\n'", "foobar")
        dc2 = self.DC(bar, r"/bin/echo -ne 'hello world\n'", "foobar")
        dc3 = self.DC(baz, r"/bin/echo -ne 'hello world\n'", "foobar")
        self.assertEqual(dc1, dc1)
        self.assertEqual(dc2, dc2)
        self.assertEqual(dc1, dc2)
        self.assertEqual(dc3, dc3)
        self.assertFalse(dc3 == dc1)
        self.assertFalse(dc3 == dc2)

    def test_output(self):
        foo = object()
        dc = self.DC(foo, r"/bin/echo -ne 'hello world\n'", "foobar")
        self.assertNotEqual(len(str(dc)), 0)
        self.assertNotEqual(len(repr(dc)), 0)

    def test_parse_empty(self):
        pcn = self.DC.parse_container_name
        self.assertRaises(ValueError, pcn, '')
        self.assertRaises(ValueError, pcn, ' ')
        self.assertRaises(ValueError, pcn, '\t    ')
        self.assertRaises(ValueError, pcn, '\r')

    def test_parse_invalid(self):
        pcn = self.DC.parse_container_name
        self.assertRaises(ValueError, pcn, ',')
        self.assertRaises(ValueError, pcn, '/')
        self.assertRaises(ValueError, pcn, ',/')
        self.assertRaises(ValueError, pcn, ',/,')
        self.assertRaises(ValueError, pcn, '/,/')
        self.assertRaises(ValueError, pcn, 'a/a,b/b,c/c')
        self.assertRaises(ValueError, pcn, 'a,b,c')
        self.assertRaises(ValueError, pcn, ',b/c')
        self.assertRaises(ValueError, pcn, 'a/b,,c/d')
        self.assertRaises(ValueError, pcn, 'a / b , , c/d')

    def test_parse_short(self):
        pcn = self.DC.parse_container_name
        self.assertRaises(ValueError, pcn, 'a,a')
        self.assertRaises(ValueError, pcn, 'a/a')

    def test_parse_valid(self):
        pcn = self.DC.parse_container_name
        self.assertEqual(pcn('a'), ('a', None))
        self.assertEqual(pcn('a,b/c'), ('a', [('b', 'c')]))
        self.assertEqual(pcn('b/c,a'), ('a', [('b', 'c')]))
        self.assertEqual(pcn('a/b,c,d/e'), ('c', [('a', 'b'), ('d', 'e')]))


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


# Just pack whatever args received into attributes
class FakeCmdResult(object):

    def __init__(self, **dargs):
        for key, val in dargs.items():
            setattr(self, key, val)


# Don't actually run anything!
def run(command, *_args, **_dargs):
    command = str(command)
    if 'inspect' in command:
        return FakeCmdResult(command=command.strip(),
                             stdout="""[{
    "ID": "abf8c40b19e353ff1f67e3a26a967c14944b07b8f5aceb752f781ffca285a2a9",
    "Created": "2014-03-26T13:42:42.676316455Z",
    "Path": "/bin/bash",
    "Args": [],
    "Config": {
        "Hostname": "28a7fbe6d375",
        "Domainname": ""
    }
}]""",
                             stderr='',
                             exit_status=0,
                             duration=1.21)
    return FakeCmdResult(command=command.strip(),
                         stdout=r"""
CONTAINER ID                                                       IMAGE                             COMMAND                                            CREATED             STATUS              PORTS                                            NAMES                                                       SIZE
ac8c9fa367f96e10cbfc7927dd4048d7db3e6d240d201019c5d4359795e3bcbe   busybox:latest                    "/bin/sh -c echo -ne "hello world\n"; sleep 10m"   5 minutes ago       Up 79 seconds                                                        cocky_albattani                                             77 B
ef0fe72271778aefcb5cf6015f30067fbe01f05996a123037f65db0b82795915   busybox:latest                    "/bin/sh -c echo -ne "world hello\n"; sleep 10m"   82 seconds ago      Up 61 seconds       4.3.2.1:4321->1234/bar, 1.2.3.4:1234->4321/foo   berserk_bohr                                                55 B
849915d551d80edce7698de91852c06bbbb7a67fe0968a3c0c246e6f25f81017   busybox:latest                    "/bin/sh -c echo -ne "hello world\n"; sleep 10m"   28 seconds ago      Up 16 seconds       1.2.3.4:1234->4321/foo, 0.0.0.0:5678->8765/tcp   berserk_bohr                                                77 B
c0c35064e4d2bdcf86e6fd83e0de2e599473c12a6599415a9a021bdf382a3589   busybox:latest                    "/bin/sh -c echo -ne "hello world\n""              5 minutes ago       Exit 0                                                               lonely_poincare                                             77 B
3723b1b0abd7be84316ce7824e68cb7af090416296c539a28d169495f44a6319   busybox:latest                    "/bin/bash -c echo -ne "hello world\n""            6 minutes ago       Exit 1                                                               clever_brattain                                             77 B
abf8c40b19e353ff1f67e3a26a967c14944b07b8f5aceb752f781ffca285a2a9   10.16.71.105:5000/fedora:latest   /bin/bash                                          22 hours ago        Exit 0                                                               child0/alias0,child1/alias1,child2/alias2,suspicious_pare   77 B
gfjggkkg9049iewm430oitjg09fd09094jte0re8g5gcgbg5ge7e15f6a2gtgggg   foobar                            /bin/bash                                          1 decade ago        Exit 99                                                              child0/alias0,infernal_github,child1/alias1,child2/alias2   77 B
e1820ef428b51a95c963353cc4ce6b57ea0a20c44537a8336792510713dfe524   10.16.71.105:5000/fedora:latest   /bin/bash                                          22 hours ago        Exit 0                                                               thirsty_mccarthy                                            77 B
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
mock('autotest.client.shared.utils')
mock('autotest.client.job')
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)
setattr(mock('autotest.client.shared.version'), 'get_version',
        lambda: version.AUTOTESTVERSION)

import version


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
        dcc = self.containers.DockerContainers(self.fake_subtest)
        cl = dcc.list_containers()
        self.assertEqual(len(cl), 8)

        metadata = dcc.json_by_long_id("ac8c9fa367f96e10cbfc7927dd4048d7db3"
                                       "e6d240d201019c5d4359795e3bcbe")
        self.assertEqual(metadata[0]['Config']['Hostname'], "28a7fbe6d375")

        self.assertNotEqual(len(dcc.json_by_name("suspicious_pare")), 0)

    def test_noports(self):
        dcc = self.containers.DockerContainers(self.fake_subtest)
        short_id = "ac8c9fa367f9"
        cl = [c for c in dcc.list_containers() if c.cmp_id(short_id)]
        self.assertEqual(len(cl), 1)
        self.assertEqual(cl[0].ports, "")

    def test_ports(self):
        from networking import ContainerPort
        dcc = self.containers.DockerContainers(self.fake_subtest)
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

    def test_links1(self):
        dcc = self.containers.DockerContainers(self.fake_subtest)
        long_id = ("abf8c40b19e353ff1f67e3a26a967"
                   "c14944b07b8f5aceb752f781ffca285a2a9")
        cnt = dcc.list_containers_with_cid(long_id)[0]
        self.assertEqual(cnt.container_name, "suspicious_pare")
        for i in range(3):
            t = ("child%d" % i, "alias%d" % i)
            self.assertEqual(cnt.links[i], t)

    def test_links2(self):
        dcc = self.containers.DockerContainers(self.fake_subtest)
        long_id = ("gfjggkkg9049iewm430oitjg09f"
                   "d09094jte0re8g5gcgbg5ge7e15f6a2gtgggg")
        cnt = dcc.list_containers_with_cid(long_id)[0]
        self.assertEqual(cnt.container_name, "infernal_github")
        for i in range(3):
            t = ("child%d" % i, "alias%d" % i)
            self.assertEqual(cnt.links[i], t)

    def test_longids(self):
        dcntr = self.containers.DockerContainers(self.fake_subtest)
        expected = ("ac8c9fa367f96e10cbfc7927dd4048d7"
                    "db3e6d240d201019c5d4359795e3bcbe",

                    "ef0fe72271778aefcb5cf6015f30067f"
                    "be01f05996a123037f65db0b82795915",

                    "849915d551d80edce7698de91852c06b"
                    "bbb7a67fe0968a3c0c246e6f25f81017",

                    "c0c35064e4d2bdcf86e6fd83e0de2e59"
                    "9473c12a6599415a9a021bdf382a3589",

                    "3723b1b0abd7be84316ce7824e68cb7a"
                    "f090416296c539a28d169495f44a6319",

                    "abf8c40b19e353ff1f67e3a26a967c14"
                    "944b07b8f5aceb752f781ffca285a2a9",

                    "e1820ef428b51a95c963353cc4ce6b57"
                    "ea0a20c44537a8336792510713dfe524")

        self.assertEqual(len(dcntr.list_container_ids()), 8)
        for exp in expected:
            self.assertTrue(exp in dcntr.list_container_ids())

if __name__ == '__main__':
    unittest.main()
