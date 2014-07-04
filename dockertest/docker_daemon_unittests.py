#!/usr/bin/env python

import json
import unittest
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


class DDTestBase(unittest.TestCase):

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

if __name__ == '__main__':
    unittest.main()
