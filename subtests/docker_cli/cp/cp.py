r"""
Summary
----------

Simple tests that check the the ``docker cp`` command.  The ``simple``
subtest verifies content creation and exact match after cp.  The
``every_last`` verifies copying many hundreds of files from a
stopped container to the host.

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

Configuration
---------------------------------
*  The ``name_prefix`` option is used for naming test containers
*  Directory/file prefixes to skip are listed as **quoted** CSV
   to the ``exclude_paths`` option
*  The ``exclude_symlinks`` yes/no option will skip trying to
   copy any files which are symlinks in the container.
*  The ``max_files`` option will stop copying after this many
   files.
"""

from StringIO import StringIO
import pickle
import inspect
import os
import os.path
from autotest.client import utils
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.containers import DockerContainers
from dockertest.environment import set_selinux_context
import hashlib


class cp(SubSubtestCaller):
    pass


class CpBase(SubSubtest):

    def initialize(self):
        super(CpBase, self).initialize()
        set_selinux_context(self.tmpdir)
        dc = self.sub_stuff['dc'] = DockerContainers(self, "cli")
        self.sub_stuff['di'] = DockerImages(self, "cli")
        container_name = dc.get_unique_name()
        self.sub_stuff['container_name'] = container_name
        fqin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['fqin'] = fqin

    def cleanup(self):
        super(CpBase, self).cleanup()
        # self.tmpdir will be automatically cleaned
        if self.config['remove_after_test']:
            DockerCmd(self, 'rm',
                      ["--force", self.sub_stuff['container_name']]).execute()


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
        cpfile = '/tmp/' + utils.generate_random_string(8)
        self.sub_stuff['cpfile'] = cpfile
        cmd = '\'echo "%s" > %s && md5sum %s\'' % (contents, cpfile, cpfile)
        subargs.append(cmd)
        nfdc = NoFailDockerCmd(self, 'run', subargs)
        cmdresult = nfdc.execute()
        self.sub_stuff['cpfile_md5'] = cmdresult.stdout.split()[0]

    def run_once(self):
        super(simple, self).run_once()
        # build arg list and execute command
        subargs = ["%s:%s" % (self.sub_stuff['container_name'],
                              self.sub_stuff['cpfile'])]
        subargs.append(self.tmpdir)
        nfdc = NoFailDockerCmd(self, "cp", subargs,
                               timeout=self.config['docker_timeout'])
        nfdc.execute()
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
        self.failif(self.sub_stuff['cpfile_md5'] != copied_md5,
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
    dump(data, stdout, 2)


class every_last(CpBase):

    def container_files(self, fqin):
        """
        Returns a list of tuples as from os.walk() inside fqin
        """
        code = ('%s\nall_files([%s], %s)'
                % (inspect.getsource(all_files),
                   self.config['exclude_paths'],
                   self.config['exclude_symlinks']))
        subargs = ["--net=none",
                   "--name=%s" % self.sub_stuff['container_name'],
                   "--attach=stdout",
                   fqin,
                   "python -c '%s'" % code]
        # Data transfered over stdout, don't log it!
        nfdc = NoFailDockerCmd(self, "run", subargs, verbose=False)
        nfdc.quiet = True
        self.logdebug("Executing %s", nfdc.command)
        nfdc.execute()
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
        self.loginfo("Testing copy of %d files from container" % total)
        self.sub_stuff['results'] = {}  # cont_path -> cmdresult
        # Avoid excessive logging
        nfdc = NoFailDockerCmd(self, 'cp', verbose=False)
        nfdc.quiet = True
        nfiles = 0
        for index, srcfile in enumerate(self.sub_stuff['lastfiles']):
            if index % 100 == 0:
                self.loginfo("Copied %d of %d", index, total)
            cont_path = "%s:%s" % (self.sub_stuff['container_name'], srcfile)
            host_path = self.tmpdir
            host_fullpath = os.path.join(host_path, os.path.basename(srcfile))
            nfdc.subargs = [cont_path, host_path]
            nfdc.execute()
            self.failif(not os.path.isfile(host_fullpath),
                        "Not a file: '%s'" % host_fullpath)
            nfiles += 1
            if nfiles >= self.config['max_files']:
                break
