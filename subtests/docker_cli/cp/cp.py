r"""
Summary
----------

Simple tests that check the the ``docker cp`` command.  The ``simple``
subtest verifies content creation and exact match after cp.  The
``every_last`` subtest verifies copying many hundreds of files from a
stopped container to the host.  The ``volume_mount`` subtest verifies
https://github.com/docker/docker/issues/27773

Operational Summary
--------------------
#. Look for an image or container
#. Run the docker cp command on it
#. Make sure the file was successfully copied

Prerequisites
-------------------------------------
*  Docker daemon is running and accessible by it's unix socket.
*  Docker image with fairly complex, deeply nested directory
   structure.
"""

from StringIO import StringIO
import pickle
import hashlib
import inspect
import os.path
from autotest.client import utils
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.output import mustpass
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.containers import DockerContainers
from dockertest.environment import set_selinux_context


class cp(SubSubtestCaller):
    pass


class CpBase(SubSubtest):

    def initialize(self):
        super(CpBase, self).initialize()
        set_selinux_context(self.tmpdir)
        dc = self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['di'] = DockerImages(self)
        container_name = dc.get_unique_name()
        self.sub_stuff['container_name'] = container_name
        fqin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['fqin'] = fqin

    def cleanup(self):
        super(CpBase, self).cleanup()
        # self.tmpdir will be automatically cleaned
        remove_after_test = self.config['remove_after_test']
        # Due to problem with selinux it is necessary to check container_name.
        if remove_after_test and 'container_name' in self.sub_stuff:
            dc = self.sub_stuff['dc']
            dc.clean_all([self.sub_stuff['container_name']])


class simple(CpBase):

    def initialize(self):
        super(simple, self).initialize()
        subargs = ['--name=%s' % self.sub_stuff["container_name"]]
        subargs.append(self.sub_stuff['fqin'])
        subargs.append('/bin/bash')
        subargs.append('-c')
        contents = utils.generate_random_string(12)
        self.sub_stuff['file_contents'] = contents
        # /tmp file inside container
        cpfile = utils.generate_random_string(8)
        self.sub_stuff['cpfile'] = cpfile
        cmd = '\'echo "%s" > %s && md5sum %s\'' % (contents, cpfile, cpfile)
        subargs.append(cmd)
        nfdc = DockerCmd(self, 'run', subargs)
        cmdresult = mustpass(nfdc.execute())
        self.sub_stuff['cpfile_md5'] = cmdresult.stdout.split()[0]

    def run_once(self):
        super(simple, self).run_once()
        # build arg list and execute command
        subargs = ["%s:%s" % (self.sub_stuff['container_name'],
                              self.sub_stuff['cpfile'])]
        subargs.append(self.tmpdir)
        nfdc = DockerCmd(self, "cp", subargs,
                         timeout=self.config['docker_timeout'])
        mustpass(nfdc.execute())
        copied_path = "%s/%s" % (self.tmpdir,
                                 self.sub_stuff['cpfile'].split('/')[-1])
        self.sub_stuff['copied_path'] = copied_path

    def postprocess(self):
        super(simple, self).postprocess()
        self.verify_files_identical(self.sub_stuff['cpfile'],
                                    self.sub_stuff['copied_path'])

    def verify_files_identical(self, docker_file, copied_file):
        with open(copied_file, 'r') as copied_content:
            data = copied_content.read()
        copied_md5 = hashlib.md5(data).hexdigest()
        self.failif_ne(self.sub_stuff['cpfile_md5'], copied_md5,
                       "Copied file '%s' does not match docker file "
                       "'%s'." % (copied_file, docker_file))
        self.loginfo("Copied file matches docker file.")


# Turned into code string by every_last.container_files()
# Must re-import needed modules and be top-level because
# inspect.getsource() preserves indentation)
def all_files(exclude_paths, exclude_symlinks=False):
    from os import walk
    from os.path import islink
    from os.path import join
    from pickle import dump
    from sys import stdout
    data = []
    for dp, dn, fl in walk("/"):
        skip = False
        for exclude_path in exclude_paths:
            if dp.startswith(exclude_path):
                skip = True
                break
        if not skip:
            if exclude_symlinks:
                fl = [fi
                      for fi in fl
                      if not islink(join(dp, fi))]
            data.append((dp, dn, fl))
    # python3: stdout is str-only, we need a binary-capable file object
    outfile = stdout
    if hasattr(stdout, "buffer"):
        outfile = stdout.buffer
    dump(data, outfile, 2)


class every_last(CpBase):

    def container_files(self, fqin):
        """
        Returns a list of tuples as from os.walk() inside fqin
        """
        python_path = self.config['python_path']
        code = ('%s\nall_files([%s], %s)'
                % (inspect.getsource(all_files),
                   self.config['exclude_paths'],
                   self.config['exclude_symlinks']))
        subargs = ["--net=none",
                   "--name=%s" % self.sub_stuff['container_name'],
                   "--attach=stdout",
                   fqin,
                   "%s -c '%s'" % (python_path, code)]
        nfdc = DockerCmd(self, "run", subargs)
        nfdc.quiet = True
        self.logdebug("Executing %s", nfdc.command)
        mustpass(nfdc.execute())
        return pickle.load(StringIO(nfdc.stdout))

    def initialize(self):
        super(every_last, self).initialize()
        # list of tuples as generated by os.walk('/') inside container
        oswalk = self.container_files(self.sub_stuff['fqin'])
        # Grab the last filename entry from each directory
        self.sub_stuff['lastfiles'] = [os.path.join(dp, fl[-1])
                                       for (dp, _, fl) in oswalk
                                       if len(fl) > 0]

    def run_once(self):
        super(every_last, self).run_once()
        total = len(self.sub_stuff['lastfiles'])
        self.sub_stuff['expected_total'] = total
        self.failif(total < self.config['max_files'],
                    "Max files number expected : %d,"
                    "exceeds container total has : %d"
                    % (self.config['max_files'], total))
        self.loginfo("Testing copy of %d files from container" % total)
        self.sub_stuff['results'] = {}  # cont_path -> cmdresult
        nfdc = DockerCmd(self, 'cp')
        nfdc.quiet = True
        nfiles = 0
        for index, srcfile in enumerate(self.sub_stuff['lastfiles']):
            if index % 100 == 0:
                self.loginfo("Copied %d of %d", nfiles, total)
            cont_path = "%s:%s" % (self.sub_stuff['container_name'], srcfile)
            host_path = self.tmpdir
            host_fullpath = os.path.join(host_path, os.path.basename(srcfile))
            nfdc.subargs = [cont_path, host_path]
            mustpass(nfdc.execute())
            self.failif(not os.path.isfile(host_fullpath),
                        "Not a file: '%s'" % host_fullpath)
            nfiles += 1
            self.sub_stuff['nfiles'] = nfiles
            if nfiles >= self.config['max_files']:
                self.loginfo("Configuration max %d, Copied %d of %d"
                             % (self.config['max_files'], nfiles, total))
                break

    def postprocess(self):
        super(every_last, self).postprocess()
        self.verify_files_number(self.sub_stuff['nfiles'],
                                 self.config['max_files'])

    def verify_files_number(self, copied_number, expected_number):
        self.failif(copied_number < expected_number,
                    "copied %d files not equal max files %d"
                    % (copied_number, expected_number))

        self.loginfo("Success, copied %d files from container, "
                     "expected number from configuration %d"
                     % (copied_number, expected_number))


class volume_mount(CpBase):
    """
    Regression between docker-1.10.3 and 1.12.

    See: https://bugzilla.redhat.com/show_bug.cgi?id=1402086
         https://github.com/docker/docker/issues/27773
    """

    def initialize(self):
        super(volume_mount, self).initialize()

        vol = 'v_' + utils.generate_random_string(8)
        subargs = ['create', '--name', vol]
        mustpass(DockerCmd(self, 'volume', subargs).execute())
        self.sub_stuff['volume_name'] = vol

        # First container: bind-mounts new volume, then unpacks two
        # tarballs into it. I don't know why it has to be two tarballs
        # and not one, but the tar thing (vs plain copy) has to do
        # with pivot_root. Whatever that is.
        c1 = DockerContainers(self).get_unique_name(prefix='c1_')
        # Path is not configurable because it's hardcoded in the tarballs
        vol_binding = vol + ':/.imagebuilder-transient-mount'
        subargs = ['--name', c1, '-v', vol_binding, 'busybox']
        mustpass(DockerCmd(self, 'create', subargs).execute())
        self.sub_stuff['container1'] = c1
        for ab in ['a', 'b']:
            tar_file = 'cp_volume_mount_data_%s.tar' % ab
            tar_path = os.path.join(self.parent_subtest.bindir, tar_file)
            # Failure mode only happens if cp is via redirected stdin.
            docker_path = self.config['docker_path']
            utils.run("%s cp - %s:/ < %s" % (docker_path, c1, tar_path))

        # Second container also bind-mounts the volume, but directly
        # through the host filesystem.
        subargs = ['inspect', '-f', '"{{ .Mountpoint }}"', vol]
        inspect_cmd = mustpass(DockerCmd(self, 'volume', subargs).execute())
        mp = inspect_cmd.stdout.strip()

        c2 = DockerContainers(self).get_unique_name(prefix='c2_')
        subargs = ['--name', c2,
                   '-v', mp + '/0:/mountdir:Z',
                   '-v', mp + '/1:/mountfile:Z',
                   'busybox', 'cat', '/mountfile']
        mustpass(DockerCmd(self, 'create', subargs).execute())
        self.sub_stuff['container2'] = c2

    def run_once(self):
        super(volume_mount, self).run_once()
        subargs = ['-a', self.sub_stuff['container2']]
        # This is the command that fails in broken docker-1.12 builds
        result = mustpass(DockerCmd(self, 'start', subargs).execute())
        self.sub_stuff['start_result'] = result

    def postprocess(self):
        super(volume_mount, self).postprocess()
        self.failif_not_in('value3b', self.sub_stuff['start_result'].stdout)

    def cleanup(self):
        super(volume_mount, self).cleanup()
        for key in ['container1', 'container2']:
            if key in self.sub_stuff:
                subargs = ['-f', self.sub_stuff[key]]
                DockerCmd(self, 'rm', subargs).execute()

        if 'volume_name' in self.sub_stuff:
            vol = self.sub_stuff['volume_name']
            DockerCmd(self, 'volume', ['rm', vol]).execute()

        self.stuff['di'].clean_all(['busybox'])
