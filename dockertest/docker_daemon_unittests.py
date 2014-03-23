#!/usr/bin/env python

import json
import unittest

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
        self.assertEqual(i.get_json('bar'), [{u'foo':u'bar'}])
        self.assertEqual(i.interface, None)

if __name__ == '__main__':
    unittest.main()
