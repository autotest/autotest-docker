r"""
Summary
-------

Test podman mount and umount

Operational Summary
-------------------

#. Run a container that creates a specially crafted file
#. Run podman mount
#. Access the desired file within that mount point, verify it
#. Run podman umount
#. Confirm that the file is no longer accessible
"""

import os
from autotest.client import utils
from dockertest.output import OutputGood, mustpass
from dockertest.output import DockerVersion
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.containers import DockerContainers
from dockertest.xceptions import DockerTestError, DockerTestNAError
from dockertest import subtest


class mount(subtest.SubSubtestCaller):
    pass

class mount_base(subtest.SubSubtest):

    def initialize(self):
        if not DockerVersion().is_podman:
            raise DockerTestNAError
        self._run_container()

    def _run_container(self):
        filename = 'rand_%s.txt' % utils.generate_random_string(8)
        filedata = utils.generate_random_string(32)
        fqin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['dc'] = dc = DockerContainers(self)
        c_name = dc.get_unique_name()
        subargs = [ '--name', c_name, fqin,
                    'bash', '-c', '\'echo "%s" >/%s\'' % (filedata, filename) ]
        mustpass(DockerCmd(self, 'run', subargs).execute())

        self.sub_stuff['c_name'] = c_name
        self.sub_stuff['cid'] = dc.list_containers_with_name(c_name)[0].long_id
        self.sub_stuff['filename'] = filename
        self.sub_stuff['filedata'] = filedata

    def _run_mount(self, args):
        cmd = DockerCmd(self, 'mount', args)
        results = mustpass(cmd.execute())
        return results.stdout.strip()

    def postprocess(self):
        super(mount_base, self).postprocess()
        mountpoint = self.sub_stuff['mountpoint']
        filepath = os.path.join(mountpoint, self.sub_stuff['filename'])
        self.failif(not os.path.isdir(mountpoint),
                    "Mount point does not exist: %s" % mountpoint)
        self.failif(not os.path.isfile(filepath),
                    "File not found: %s" % filepath)
        # Read file, compare contents
        actual = open(filepath, 'r').read().strip()
        self.failif_ne(actual, self.sub_stuff['filedata'],
                       "Contents of magic file")

    def cleanup(self):
        super(mount_base, self).cleanup()
        dc = DockerContainers(self)
        c_name = self.sub_stuff.get("c_name")
        if c_name:
            dc.clean_all([c_name])


class mount_by_name(mount_base):

    def run_once(self):
        super(mount_by_name, self).run_once()
        c_name = self.sub_stuff['c_name']
        self.sub_stuff['mountpoint'] = self._run_mount([c_name])


class mount_by_cid(mount_base):

    def run_once(self):
        super(mount_by_cid, self).run_once()
        cid = self.sub_stuff['cid']
        self.sub_stuff['mountpoint'] = self._run_mount([cid])


class mount_twice(mount_base):

    def run_once(self):
        super(mount_twice, self).run_once()
        m1 = self._run_mount([self.sub_stuff['c_name']])
        m2 = self._run_mount([self.sub_stuff['cid']])
        self.failif_ne(m1, m2, 'mountpoint for same container')
        self.sub_stuff['mountpoint'] = m1


class mount_with_no_args(mount_by_name):
    """ confirm that 'podman mount' returns all mounted points """

    def postprocess(self):
        # super() checks that file exists as expected
        super(mount_with_no_args, self).postprocess()

        # Now run just mount, see if we get what we expect
        cmd = DockerCmd(self, 'mount', ['--notruncate'])
        results = mustpass(cmd.execute())
        (cid, mountpoint) = results.stdout.strip().split()
        self.failif_ne(cid, self.sub_stuff['cid'], 'output of podman-mount')
        self.failif_ne(mountpoint, self.sub_stuff['mountpoint'],
                       'output of podman-mount')


class umount_umounts(mount_by_name):

    def postprocess(self):
        # super() checks that file exists as expected
        super(umount_umounts, self).run_once()

        # We now run umount, and file should no longer exist
        cmd = DockerCmd(self, 'umount', [self.sub_stuff['cid']])
        results = mustpass(cmd.execute())

        # The mountpoint itself should exist, because the container
        # hasn't been removed. But there should be no files in it.
        mountpoint = self.sub_stuff['mountpoint']
        filepath = os.path.join(mountpoint, self.sub_stuff['filename'])
        self.failif(os.path.exists(filepath),
                    "filepath exists after umount: %s" % filepath)
        contents = os.listdir(mountpoint)
        self.failif_ne(contents, [], "sdfsdf")
