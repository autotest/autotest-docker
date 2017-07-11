#!/usr/bin/env python

import json
import unittest2
import sys
import types


def mock(mod_path):
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

# Simulate utils.run(). Individual tests prime us with predetermined
# results for each invocation of utils.run.
FAKERUN_RESULTS = []

def fakerun_setup(**kwargs):
    fake_cmd_result = { 'command': '',
                        'stdout': '',
                        'stderr': '',
                        'exit_status': 0,
                        'duration': 0.1 }
    for k in fake_cmd_result.keys():
        if k in kwargs:
            fake_cmd_result[k] = kwargs[k]
    FAKERUN_RESULTS.append(FakeCmdResult(**fake_cmd_result))

def fakerun(command, *_args, **_dargs):
    return FAKERUN_RESULTS.pop(0)


# Mock module and exception class in one stroke
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)
mock('autotest.client.utils')
mock('autotest.client.shared.utils')
mock('autotest.client.shared.error')
mock('autotest.client.shared.service')
setattr(mock('autotest.client.utils'), 'run', fakerun)


class DDTestBase(unittest2.TestCase):

    def setUp(self):
        import docker_daemon
        self.dd = docker_daemon


class DDTest(DDTestBase):

    def test_client_base(self):
        cb = self.dd.ClientBase('uri')
        self.assertEqual(cb.interface, None)
        self.assertEqual(cb.uri, 'uri')
        self.assertRaises(NotImplementedError, cb.get, 'foo')
        self.assertRaises(NotImplementedError, cb.value_to_json, 'bar')
        self.assertRaises(NotImplementedError, cb.get_json, 'foobar')

    def test_client_subclass(self):
        class c(self.dd.ClientBase):

            def get(self, resource):
                return (self.uri, resource)

            @staticmethod
            def value_to_json(value):
                return json.loads('[{"%s":"%s"}]' % value)
        i = c('foo')
        self.assertEqual(i.get_json('bar'), [{u'foo': u'bar'}])
        self.assertEqual(i.interface, None)


class TestStringEdit(unittest2.TestCase):
    """
    Tests for edit_option_string()
    """

    # Various combinations of inputs, and their expected output for
    # the edit_options_string() function.
    # Thanks to  https://gist.github.com/encukou/10017915  for documentation
    # on unittest2.subTest()
    string_edit_tests = [
        # original         remove          add             expected
        ['abc',            None,           None,           'abc'],
        ['"abc"',          None,           None,           '"abc"'],
        ['"abc"',          "abc",          "def",          '"def"'],
        ["'--a --b --c'",  '--a',          None,           "'--b --c'"],
        ["'--a --b --c'",  '--b',          None,           "'--a  --c'"],
        ["'--a --b --c'",  '--c',          None,           "'--a --b'"],
        ["'--a --b --c'",  ['--a', '--c'], None,           "'--b'"],
        ["'--a --c'",      None,           ['--a', '--b'], "'--a --c --b'"],
    ]

    def test_edit_options_string(self):
        import docker_daemon
        for (opts_in, remove, add, opts_out) in self.string_edit_tests:
            with self.subTest(name="%s -<%s> +<%s>" % (opts_in, remove, add)):
                s_in = 'OPTIONS=%s\n' % opts_in
                expected = 'OPTIONS=%s\n' % opts_out
                actual = docker_daemon.edit_options_string(s_in, remove, add)
                self.assertEqual(actual, expected)

    def test_bad_input_no_prefix(self):
        import docker_daemon
        self.assertRaises(ValueError,
                          docker_daemon.edit_options_string, "OPTINOS=hi")

    def test_bad_input_mismatched_quotes(self):
        import docker_daemon
        self.assertRaises(ValueError,
                          docker_daemon.edit_options_string,
                          "OPTIONS='missing end quote")


class TestWhichDocker(unittest2.TestCase):
    """
    Tests for which_docker()
    """

    def test_default(self):
        """
        Default to 'docker' when systemctl output isn't helpful
        """
        import docker_daemon
        fakerun_setup(stdout="")
        self.assertEqual(docker_daemon.which_docker(), 'docker', 'default')

    def test_full_systemctl_output(self):
        """
        Parse realistic systemctl output
        """
        import docker_daemon
        fakerun_setup(stdout="""UNIT                       LOAD   ACTIVE SUB     DESCRIPTION
auditd.service             loaded active running Security Auditing Service
chronyd.service            loaded active running NTP client/server
container-engine.service   loaded active running Container Engine service
crond.service              loaded active running Command Scheduler
dbus.service               loaded active running D-Bus System Message Bus
dm-event.service           loaded active running Device-mapper event daemon
firewalld.service          loaded active running firewalld - dynamic firewall daemon
getty@tty1.service         loaded active running Getty on tty1
irqbalance.service         loaded active running irqbalance daemon
lvm2-lvmetad.service       loaded active running LVM2 metadata daemon
NetworkManager.service     loaded active running Network Manager
nginx.service              loaded active running The nginx HTTP and reverse proxy server
polkit.service             loaded active running Authorization Manager
postfix.service            loaded active running Postfix Mail Transport Agent
rhel-push-plugin.service   loaded active running Docker Block RHEL push plugin authZ Plugin
rhnsd.service              loaded active running LSB: Starts the Spacewalk Daemon
rhsmcertd.service          loaded active running Enable periodic update of entitlement certificates.
rsyslog.service            loaded active running System Logging Service
serial-getty@ttyS0.service loaded active running Serial Getty on ttyS0
sshd.service               loaded active running OpenSSH server daemon
systemd-journald.service   loaded active running Journal Service
systemd-logind.service     loaded active running Login Service
systemd-udevd.service      loaded active running udev Kernel Device Manager
tuned.service              loaded active running Dynamic System Tuning Daemon

LOAD   = Reflects whether the unit definition was properly loaded.
ACTIVE = The high-level unit activation state, i.e. generalization of SUB.
SUB    = The low-level unit activation state, values depend on unit type.

24 loaded units listed. Pass --all to see loaded but inactive units, too.
To show all installed unit files use 'systemctl list-unit-files'.
""")
        expect = "container-engine"
        actual = docker_daemon.which_docker()
        self.assertEqual(actual, expect, "which_docker()")


class TestSystemdShow(unittest2.TestCase):
    """
    Tests for systemd_show()
    """

    def test_simple(self):
        """
        The usual case: systemctl responds with a 'Property=XXX' one-liner
        """
        import docker_daemon

        expect = 'baz'
        fakerun_setup(stdout="\n")                      # for which_docker()
        fakerun_setup(stdout="FooBar=%s\n" % expect)
        actual = docker_daemon.systemd_show('FooBar')

        self.assertEqual(actual, expect, "systemd_show(FooBar)")

    def test_bad_output_from_systemctl(self):
        """
        If for some reason systemctl does not return a 'Property=XXX' line
        """
        import docker_daemon

        fakerun_setup(stdout="\n")                      # for which_docker()
        fakerun_setup(stdout="UnExpectedResultWithNoEqualsSign\n")
        self.assertRaises(RuntimeError,
                          docker_daemon.systemd_show, 'FooBar')

    def test_pid(self):
        """
        docker_daemon.pid() depends on systemctl_show
        """
        import docker_daemon

        # It also checks the docker daemon command line, because it has to
        # distinguish between dockerd itself and dockerd run under runc
        # (as a container). The third fakerun_setup() simulates the
        # output of 'ps' on our pid.
        fakerun_setup(stdout="\n")                      # for which_docker()
        fakerun_setup(stdout="MainPID=12345\n")
        fakerun_setup(stdout="/usr/bin/dockerd --add-runtime ...\n")

        self.assertEqual(docker_daemon.pid(), 12345, 'daemon pid')


if __name__ == '__main__':
    unittest2.main()
