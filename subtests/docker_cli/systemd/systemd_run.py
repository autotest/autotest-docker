"""
To Test basic function of running container as systemd service using a
predefined settings
"""

import time
import socket
from os.path import join
from shutil import copy
from shutil import copyfile
from autotest.client import utils
from autotest.client.shared.utils import is_port_free
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.xceptions import DockerTestError
from systemd import systemd_base


class systemd_run(systemd_base):

    def initialize(self):
        # edit unitfile & copy it to /etc/systemd/system/
        super(systemd_run, self).initialize()
        run_dict = {'name': self.config['image_name']}
        self.sed_file(run_dict)
        copyfile(self.sub_stuff['tmpdirf'], self.sub_stuff['unitf_dst'])
        # copy Dockerfile & p4321-server.py to tmpdir and edit Dockerfile
        tmpdir = self.sub_stuff['tmpdir']
        self.sub_stuff['tmpdirf'] = join(tmpdir, 'Dockerfile')
        for f in 'Dockerfile', 'p4321-server.py':
            copy(join(self.sub_stuff['bindir'], f), tmpdir)
        dkrfl_dict = {'base_img': self.config['img_frm']}
        self.sed_file(dkrfl_dict)
        # build image using edited Dockerfile in tmpdir
        dkrcmd = DockerCmd(self, 'build', [self.config['build_opt'], tmpdir])
        mustpass(dkrcmd.execute())

    def run_once(self):
        self.sysd_action('daemon-reload')
        self.sysd_action('start', self.config['sysd_unit_file'])

    def postprocess(self):
        super(systemd_run, self).postprocess()
        host = 'localhost'
        port = 4321
        utils.wait_for(lambda: not is_port_free(port, host), 10)
        time_from_socket = self.read_socket(host, port)
        self.failif(not time_from_socket.isdigit(),
                    "Data received from container is non-numeric: '%s'"
                    % time_from_socket)

    @staticmethod
    def read_socket(host, port):
        max_read_tries = 10
        num_read_try = max_read_tries
        while num_read_try:
            # using timeout 13-sec as it's 1-sec longer than two DNS timeouts
            skt = socket.create_connection((host, port), 13)
            skt.settimeout(2.0)
            try:
                time_from_socket = skt.recv(512).strip()
                if time_from_socket:
                    skt.shutdown(socket.SHUT_RDWR)
                    return time_from_socket
                num_read_try -= 1
            except socket.timeout:
                pass
            finally:
                time.sleep(1.0)
                try:
                    skt.shutdown(socket.SHUT_RDWR)
                except socket.error:
                    pass
        raise DockerTestError("Failed to read from socket with %d tries"
                              % max_read_tries)
