"""
Provides helpers for frequently used docker networking operations.

This module defines several independent interfaces using an abstract-base-class
pattern.   They are extended through a few subclasses to meet basic needs.

Where/when ***possible***, both parameters and return values follow this order
and defaults:

*  ``container_port``
*  ``host_port`` (same as container_port if unspecified)
*  ``host_ip``   (literal "0.0.0.0" if unspecified)
*  ``protocol``  (literal "tcp" if unspecified
"""

# Pylint runs from another directory, ignore relative import warnings
# pylint: disable=W0403

import re


class ContainerPort(object):
    """
    Represents a private container port mapping to public host ip, and port.
    """

    #: There will likely be several instances per container
    __slots__ = ["container_port", "host_ip",
                 "host_port", "protocol", "portstr"]

    #: Regex to help extract components from string of format
    #: <host IP>:<host port>->
    port_split_p = re.compile(r"(\d\.\d\.\d\.\d):(\d+)->(\d+)/([a-z]+)")

    def __init__(self, container_port, host_port=None,
                 host_ip="0.0.0.0", protocol="tcp"):
        """
        Initialize a new port instance from parameters

        :param container_port: Port number visible inside the container
        :param host_port: Port number on host container_Port maps to
        :param host_ip: Host interface IP host_port maps to
        :param protocol: Name of protocol for map (i.e. ``tcp`` or ``udp``)
        """
        self.container_port = int(container_port)
        if host_port is None:
            self.host_port = int(container_port)
        else:
            self.host_port = int(host_port)
        self.host_ip = host_ip
        self.protocol = protocol
        self.portstr = self.portstr_from_component(self.container_port,
                                                   self.host_port,
                                                   self.host_ip,
                                                   self.protocol)

    def __eq__(self, other):
        """
        Compare this instance to another

        :param other: An instance of this class (or subclass) for comparison.
        """
        self_val = [getattr(self, name) for name in self.__slots__]
        other_val = [getattr(other, name) for name in self.__slots__]
        for _self, _other in zip(self_val, other_val):
            if _self != _other:
                return False
        return True

    def __str__(self):
        """
        Break down port string components into a human-readable format
        """
        return ("Container (private) port: %d, Host (public) port: %d, "
                "Host (interface) IP: %s, Protocol: %s"
                 % (self.container_port, self.host_port, self.host_ip,
                    self.protocol))

    def __repr__(self):
        """
        Return python-standard representation of instance
        """
        return "ContainerPort(%s)" % str(self)

    @staticmethod
    def split_to_component(portstr):
        """
        Split published into separate component strings/numbers

        :param portstr: Port info string
        :return: Iterable of container_port, host_ip, host_port, protocol
        """
        try:
            cppsm = ContainerPort.port_split_p.match
            (host_ip, host_port,
             container_port, protocol) = cppsm(portstr).groups()
        except:
            raise ValueError("port string '%s' doesn't match "
                             "expected format" % portstr)
        return int(container_port), int(host_port), host_ip, protocol

    @staticmethod
    def portstr_from_component(container_port, host_port=None,
                               host_ip="0.0.0.0", protocol="tcp"):
        """
        Port name string from individual components.

        :param container_port: Port number visible inside the container
        :param host_port: Port number on host container_Port maps to
        :param host_ip: Host interface IP host_port maps to
        :param protocol: Name of protocol (i.e. ``tcp`` or ``udp``)
        :return: port string
        """
        if host_port is None:
            host_port = container_port
        return ("%s:%d->%d/%s" % (host_ip, host_port,
                                  container_port, protocol))

    def cmp_portstr_with_component(self, container_port, host_port=None,
                                   host_ip="0.0.0.0", protocol="tcp"):
        """
        Boolean compare instance's portstr to individual components

        :param container_port: Port number visible inside the container
        :param host_port: Port number on host container_Port maps to
        :param host_ip: Host interface IP host_port maps to
        :param protocol: Name of protocol (i.e. ``tcp`` or ``udp``)
        :return: True/False on equality
        """
        return self.portstr == self.portstr_from_component(container_port,
                                                           host_port,
                                                           host_ip, protocol)

    def cmp_portstr(self, portstr):
        """
        Compare instance's portstr to portstr parameter

        :param portstr: Port string
        :return: True/False on equality
        """
        return self.portstr == portstr
