r"""
Summary
-------

This is to test basic container as systemd service using a predefined unit
file. Image pulling, building, and running are performed.

Operational Summary
---------------------

#. Provided unitfile is edited & copied to ``/etc/systemd/system``.
#. Image is pulled using unitfile
#. Image is build using provided Dockedfile
#. Container is started/run using unitfile

Operational Detail
----------------------

systemd pull
~~~~~~~~~~~~~~~~~
#. Edit unitfile ``docker-pull.service`` & copy it to ``/etc/systemd/system``
#. Systemd service is started using this file to pull an image.
#. Systemd service is stoped and image removed

systemd build
~~~~~~~~~~~~~~~~~
#. Edit unitfile ``docker-build.service`` & copy it to ``/etc/systemd/system``
#. Edit Dockerfile
#. Systemd service is started using this file to build an image.
#. Systemd service is stoped and image removed

systemd run
~~~~~~~~~~~~~~~~~
#. Edit unitfile ``p4321.service`` and copy to ``/etc/systemd/system``
#. Edit ``Dockerfile`` and copy to test temporary directory
#. Copy a script ``p4321-server.py`` to test temporary directory
#. Built an image using the Dockerfile and script
#. Systemd starts a container using this image
#. The container writes current time to port ``4321``.
#. From host, the socket is read and the value is checked
#. Finally, container is stopped through systemd and system is cleaned up.

Prerequisites
----------------
*  Docker daemon is running
*  systemd unitfiles can be copied to ``/etc/systemd/system``
*  systemd actions of start/status/stop & daemon-reload can be performed
*  An image stated in systemd.ini can be pulled & build
"""

from os.path import join
from os import rename
from os import unlink
from shutil import copyfile
from autotest.client import utils
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.images import DockerImages
from dockertest.xceptions import DockerTestError


class systemd(SubSubtestCaller):
    pass


class systemd_base(SubSubtest):

    def initialize(self):
        super(systemd_base, self).initialize()
        self.sub_stuff['bindir'] = self.parent_subtest.bindir
        self.sub_stuff['tmpdir'] = self.tmpdir
        unitfile = self.config['sysd_unit_file']
        self.sub_stuff['unitf_dst'] = join('/etc/systemd/system', unitfile)
        self.sub_stuff['tmpdirf'] = join(self.sub_stuff['tmpdir'], unitfile)
        self.sub_stuff['dkrfl'] = join(self.sub_stuff['bindir'], 'Dockerfile')
        copyfile(join(self.sub_stuff['bindir'], unitfile),
                 self.sub_stuff['tmpdirf'])

    def run_once(self):
        self.sysd_action('daemon-reload')
        for act in 'start', 'status':
            self.sysd_action(act, self.config['sysd_unit_file'])

    def postprocess(self):
        super(systemd_base, self).postprocess()
        imgs_fulname = DockerImages(self).list_imgs_full_name()
        names_lst = [x.split(':')[0].split('/', -1)[-1] for x in imgs_fulname]
        if self.config['image_name'] not in names_lst:
            raise DockerTestError("Image %s is not present"
                                  % self.config['image_name'])

    def cleanup(self):
        super(systemd_base, self).cleanup()
        try:
            self.sysd_action('stop', self.config['sysd_unit_file'])
        except OSError:
            pass
        finally:
            unlink(self.sub_stuff['unitf_dst'])
            self.sysd_action('daemon-reload')
        DockerImages(self).clean_all([self.config['image_name']])

    @staticmethod
    def sysd_action(action, sysd_unit=None):
        command = 'systemctl {}'.format(action)
        if sysd_unit:
            command = '{} {}'.format(command, sysd_unit)
        utils.run(command, ignore_status=False)

    def sed_file(self, vars_dict):
        tmpdir_rf = self.sub_stuff['tmpdirf']
        tmpdir_wf = '{}.tmp'.format(tmpdir_rf)
        with open(tmpdir_rf, "r") as srcfile, open(tmpdir_wf, "w") as dstfile:
            dstfile.write(srcfile.read().format(**vars_dict))
        rename(tmpdir_wf, tmpdir_rf)


class systemd_build(systemd_base):

    """
    To test building an image using systemd unitfile
    """

    def initialize(self):
        # edit unitfile & copy it to /etc/systemd/system/
        super(systemd_build, self).initialize()
        build_dict = {'dockerfiledir': self.sub_stuff['bindir'],
                      'options': self.config['unit_opts'],
                      'name': self.config['image_name']}
        self.sed_file(build_dict)
        copyfile(self.sub_stuff['tmpdirf'], self.sub_stuff['unitf_dst'])
        # copy Dockerfile to tmpdir, edit, then copy to bindir for build
        self.sub_stuff['tmpdirf'] = join(self.sub_stuff['tmpdir'],
                                         'Dockerfile')
        tmpdirf = self.sub_stuff['tmpdirf']
        self.sub_stuff['dkrfl_bk'] = '{}.bk'.format(tmpdirf)
        for f in [tmpdirf, self.sub_stuff['dkrfl_bk']]:
            copyfile(self.sub_stuff['dkrfl'], f)
        dkrfl_dict = {'base_img': self.config['img_frm']}
        self.sed_file(dkrfl_dict)
        copyfile(tmpdirf, self.sub_stuff['dkrfl'])

    def cleanup(self):
        super(systemd_build, self).cleanup()
        # restore Dockerfile to its initial state
        copyfile(self.sub_stuff['dkrfl_bk'], self.sub_stuff['dkrfl'])


class systemd_pull(systemd_base):

    """
    To test pulling an image using systemd unitfile
    """

    def initialize(self):
        # edit unitfile & copy it to /etc/systemd/system/
        super(systemd_pull, self).initialize()
        pull_dict = {'name': self.config['image_name']}
        self.sed_file(pull_dict)
        copyfile(self.sub_stuff['tmpdirf'], self.sub_stuff['unitf_dst'])
