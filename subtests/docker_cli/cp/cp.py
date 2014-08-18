"""
Test output of the docker cp command

1. Look for an image or container
2. Run the docker cp command on it
3. Make sure the file was successfully copied
"""

from autotest.client import utils
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.containers import DockerContainers
import hashlib

class cp(SubSubtestCaller):
    pass

class simple(SubSubtest):

    def initialize(self):
        super(simple, self).initialize()
        dc = DockerContainers(self, "cli")
        container_name = dc.get_unique_name('cp_simple')
        self.sub_stuff['container_name'] = container_name
        subargs = ['--name=%s' % container_name]
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
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

    def cleanup(self):
        super(simple, self).cleanup()
        if self.config['remove_after_test']:
            dkrcmd = DockerCmd(self, 'rm', [self.sub_stuff['container_name']])
            dkrcmd.execute()
