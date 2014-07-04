#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import unittest


class NetworkingTestBase(unittest.TestCase):

    def setUp(self):
        import networking
        self.networking = networking
        self.CP = self.networking.ContainerPort

    def tearDown(self):
        del self.networking


class ContainerPortTest(NetworkingTestBase):

    def test_init_defaults(self):
        cp = self.CP(1234)
        self.assertEqual(cp.container_port, 1234)
        self.assertEqual(cp.host_port, cp.container_port)
        self.assertEqual(cp.host_ip, "0.0.0.0")
        self.assertEqual(cp.protocol, "tcp")
        self.assertEqual(cp.portstr, "0.0.0.0:1234->1234/tcp")

    def test_init_fullargs(self):
        cp = self.CP(4321, 1234, "1.2.3.4", "foobar")
        self.assertEqual(cp.container_port, 4321)
        self.assertEqual(cp.host_port, 1234)
        self.assertEqual(cp.host_ip, "1.2.3.4")
        self.assertEqual(cp.protocol, "foobar")
        self.assertEqual(cp.portstr, "1.2.3.4:1234->4321/foobar")

    def test_eq_ne(self):
        cp1 = self.CP(4321, 1234, "1.2.3.4", "foobar")
        cp2 = self.CP(4321, 1234, "1.2.3.4", "foobar")
        cp3 = self.CP(1234, 4321, "4.3.2.1", "barfoo")
        self.assertEqual(cp1, cp2)
        self.assertEqual(cp2, cp2)
        self.assertEqual(cp1, cp2)
        self.assertEqual(cp3, cp3)
        self.assertNotEqual(cp3, cp1)
        self.assertNotEqual(cp3, cp2)

    def test_str(self):
        container_port = 4321
        host_port = 1234
        host_ip = "1.2.3.4"
        protocol = "foobar"
        cp = self.CP(container_port, host_port, host_ip, protocol)
        cps = str(cp)
        for s in (container_port, host_port, host_ip, protocol):
            self.assertTrue(cps.count(str(s)) > 0)

    def test_cmp_portstr_with_component(self):
        container_port = 4321
        host_port = 1234
        host_ip = "1.2.3.4"
        protocol = "foobar"
        cp = self.CP(container_port, host_port, host_ip, protocol)
        self.assertTrue(cp.cmp_portstr_with_component(4321, 1234,
                                                      "1.2.3.4", "foobar"))
        self.assertFalse(cp.cmp_portstr_with_component(4321, 1234,
                                                       "1.2.3.4"))

    def test_split_to_component(self):
        # host_ip:host_port->container_port/protocol
        result = self.CP.split_to_component("4.2.2.1:5678->9876/tux")
        # container_port, host_port, host_ip, protocol
        self.assertEqual(result[0], 9876)
        self.assertEqual(result[1], 5678)
        self.assertEqual(result[2], "4.2.2.1")
        self.assertEqual(result[3], 'tux')

if __name__ == '__main__':
    unittest.main()
