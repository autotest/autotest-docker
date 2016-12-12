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

from os.path import exists, join
from os import rename, unlink
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

        # Copy unit file into place, with translations.
        bindir = self.parent_subtest.bindir
        unitfile = self.config['sysd_unit_file']
        unitfile_src = join(bindir, unitfile)
        self.sub_stuff['unitfile_dst'] = join('/etc/systemd/system', unitfile)
        self.sed_file(unitfile_src, self.sub_stuff['unitfile_dst'])

        # Dockerfile & requirements to tmp workdir (not all tests use this)
        for f in ['Dockerfile', 'p4321-server.py']:
            self.sed_file(join(bindir, f), join(self.tmpdir, f))

    def run_once(self):
        super(systemd_base, self).run_once()
        self.sysd_action('daemon-reload')
        for act in 'start', 'status':
            self.sysd_action(act, self.config['sysd_unit_file'])

    def postprocess(self):
        super(systemd_base, self).postprocess()
        image_name = self.config['image_name']
        all_images = DockerImages(self).list_imgs()
        for img_obj in all_images:
            if img_obj.cmp_greedy(repo=image_name, tag="latest"):
                return
        raise DockerTestError("Image %s:latest not found among %s" %
                              (image_name, [i.full_name for i in all_images]))

    def cleanup(self):
        super(systemd_base, self).cleanup()
        try:
            self.sysd_action('stop', self.config['sysd_unit_file'])
        except OSError:
            pass
        finally:
            unlink(self.sub_stuff['unitfile_dst'])
            self.sysd_action('daemon-reload')
        DockerImages(self).clean_all([self.config['image_name']])

    @staticmethod
    def sysd_action(action, sysd_unit=None):
        command = 'systemctl {}'.format(action)
        if sysd_unit:
            command = '{} {}'.format(command, sysd_unit)
        utils.run(command, ignore_status=False)

    def sed_file(self, path_in, path_out):
        """
        Copies path_in to path_out, replacing {xxxxx} in the source file
        with values from config settings
        """
        path_out_tmp = path_out + '.tmp'
        if exists(path_out_tmp):
            unlink(path_out_tmp)
        replace = dict(self.config)
        replace['tmpdir'] = self.tmpdir
        with open(path_in, "r") as srcfile, open(path_out_tmp, "w") as dstfile:
            dstfile.write(srcfile.read().format(**replace))
        rename(path_out_tmp, path_out)


class systemd_build(systemd_base):

    """
    To test building an image using systemd unitfile
    """
    pass


class systemd_pull(systemd_base):

    """
    To test pulling an image using systemd unitfile
    """
    pass
