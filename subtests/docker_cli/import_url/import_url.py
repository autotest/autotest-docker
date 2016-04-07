r"""
Summary
----------

Tests on tarball contents imported from a URL.  The "md5sum"
test compares imported image md5sum against a known value.

Operational Summary
----------------------
#. Import image
#. Verify if result is expected

Prerequisites
-------------------------------------------
The configured URL points to a tarball in an accepted format
by docker (plain, bzip, gzip, etc.).
"""

from os.path import basename
from os.path import join
from hashlib import md5
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.config import get_as_list
from dockertest.containers import DockerContainers
from dockertest.images import DockerImages
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.output import mustfail


class import_url(SubSubtestCaller):
    pass


class base(SubSubtest):

    def run_import(self):
        subargs = [self.config['tar_url'].strip(),
                   self.sub_stuff['import_repo']]
        cmdresult = mustpass(DockerCmd(self, 'import', subargs).execute())
        self.sub_stuff['import_cmdresult'] = cmdresult

    def run_image(self):
        # Can only cp file from containers, not repos
        subargs = ['--name=%s' % self.sub_stuff['run_name']]
        subargs += ['--detach']
        subargs += [self.sub_stuff['import_repo']]
        subargs += ['some', 'dummy', 'command']
        self.logdebug("Next docker command should fail...")
        mustfail(DockerCmd(self, 'run', subargs).execute(), 125)

    def initialize(self):
        super(base, self).initialize()
        dc = self.sub_stuff['dc'] = DockerContainers(self)
        di = self.sub_stuff['di'] = DockerImages(self)
        import_repo = di.get_unique_name()
        run_name = dc.get_unique_name()
        self.sub_stuff['run_name'] = run_name
        self.sub_stuff['import_repo'] = import_repo
        self.sub_stuff['import_cmdresult'] = None
        self.run_import()
        self.sub_stuff['run_cid'] = None
        self.run_image()

    def cleanup(self):
        super(base, self).cleanup()
        if self.config['remove_after_test']:
            preserve_fqins = get_as_list(self.config['preserve_fqins'])
            preserve_cnames = get_as_list(self.config['preserve_cnames'])
            if self.sub_stuff['import_repo'] not in preserve_fqins:
                DockerCmd(self, 'rmi',
                          [self.sub_stuff['import_repo']]).execute()
            if self.sub_stuff['run_name'] not in preserve_cnames:
                DockerCmd(self, 'rm',
                          [self.sub_stuff['run_name']]).execute()


class md5sum(base):

    def initialize(self):
        super(md5sum, self).initialize()
        self.sub_stuff['filename'] = basename(self.config['in_tar_file'])

    def run_once(self):
        super(md5sum, self).run_once()
        subargs = ['%s:%s' % (self.sub_stuff['run_name'],
                              self.config['in_tar_file']),
                   self.tmpdir]
        mustpass(DockerCmd(self, 'cp', subargs).execute())

    def postprocess(self):
        super(md5sum, self).postprocess()
        cp_file = open(join(self.tmpdir, self.sub_stuff['filename']), 'rb')
        data = cp_file.read()
        actual_md5 = md5(data).hexdigest()
        failmsg = ("File %s in tarball from %s md5"
                   % (self.sub_stuff['filename'], self.config['tar_url']))
        self.failif_ne(actual_md5, self.config['md5sum'], failmsg)
