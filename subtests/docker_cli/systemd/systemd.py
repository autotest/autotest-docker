"""
Summary
-------
Testing basic container as systemd service

Operational Summary
---------------------
This is to test container as systemd service using a predefined unit file
(``p4321.service``) and a ``script p4321-server.py``. An image is built with
this script added. Systemd starts a container using this image & the container
writes current time to port ``4321``. From host, the socket is read and the
value is checked to see if it is a digit. Finally, container is stopped
through systemd and system is cleaned up.

"""

import shutil
import time
import socket
from os.path import exists
from os import unlink
from autotest.client import utils
from autotest.client.shared.utils import is_port_free
from dockertest.subtest import Subtest
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImages
from dockertest.output import mustpass
from dockertest.xceptions import DockerTestError


class systemd(Subtest):

    def initialize(self):
        super(systemd, self).initialize()
        unit_file_srcpath = '{}{}'.format(self.bindir, '/p4321.service')
        shutil.copyfile(unit_file_srcpath, self.config['sysd_unitf_dest'])
        dkrcmd = DockerCmd(self, 'build', ['--force-rm -t',
                                           self.config['name'], self.bindir])
        mustpass(dkrcmd.execute())

    def run_once(self):
        host = 'localhost'
        port = 4321
        self.sysd_action('daemon-reload')
        self.sysd_action('start', self.config['sysd_unit_file'])
        utils.wait_for(lambda: not is_port_free(port, host), 10)
        time_from_socket = self.read_socket(host, port)
        self.failif(not time_from_socket.isdigit(),
                    "Data received from container is non-numeric: '%s'"
                    % time_from_socket)

    def cleanup(self):
        super(systemd, self).cleanup()
        filepath = self.config['sysd_unitf_dest']
        if exists(filepath):
            self.sysd_action('stop', self.config['sysd_unit_file'])
            unlink(filepath)
            self.sysd_action('daemon-reload')
        DockerImages(self).clean_all([self.config['name']])

    @staticmethod
    def sysd_action(action=None, sysd_unit=None):
        command = 'systemctl {}'.format(action)
        if sysd_unit:
            command = '{} {}'.format(command, sysd_unit)
        utils.run(command, ignore_status=False)

    @staticmethod
    def read_socket(host, port):
        max_read_tries = 10
        num_read_try = max_read_tries
        while num_read_try:
            # using timeout 13-sec as it's 1-sec longer than two DNS timeouts
            s = socket.create_connection((host, port), 13)
            s.settimeout(2.0)
            try:
                time_from_socket = s.recv(512).strip()
                if time_from_socket:
                    s.shutdown(socket.SHUT_RDWR)
                    return time_from_socket
                num_read_try -= 1
            except socket.timeout:
                pass
            time.sleep(1.0)
        raise DockerTestError("Failed to read from socket with %d tries"
                              % max_read_tries)
