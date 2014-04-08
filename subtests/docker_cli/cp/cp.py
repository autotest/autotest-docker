"""
Test output of the docker cp command

1. Look for an image or container
2. Run the docker cp command on it
3. Make sure the file was successfully copied
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from autotest.client import utils
from dockertest import subtest
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
import hashlib

class cp(subtest.Subtest):
    config_section = 'docker_cli/cp'

    def initialize(self):
        super(cp, self).initialize()
        name = self.stuff['container_name'] = utils.generate_random_string(12)
        subargs = ['--name=%s' % name]
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append('/bin/bash')
        subargs.append('-c')
        contents = utils.generate_random_string(12)
        self.stuff['file_contents'] = contents
        cpfile = '/tmp/' + utils.generate_random_string(8)
        self.stuff['cpfile'] = cpfile
        cmd = '\'echo "%s" > %s && md5sum %s\'' % (contents, cpfile, cpfile)
        subargs.append(cmd)
        nfdc = NoFailDockerCmd(self, 'run', subargs)
        cmdresult = nfdc.execute()
        self.stuff['cpfile_md5'] = cmdresult.stdout.split()[0]

    def run_once(self):
        super(cp, self).run_once()
        #build arg list and execute command
        subargs = [self.stuff['container_name'] + ":" + self.stuff['cpfile']]
        subargs.append(self.tmpdir)
        nfdc = NoFailDockerCmd(self, "cp", subargs,
                               timeout=self.config['docker_timeout'])
        nfdc.execute()
        copied_path = "%s/%s" % (self.tmpdir,
                                   self.stuff['cpfile'].split('/')[-1])
        self.stuff['copied_path'] = copied_path

    def postprocess(self):
        self.verify_files_identical(self.stuff['cpfile'],
                                    self.stuff['copied_path'])

    def verify_files_identical(self, docker_file, copied_file):
        with open(copied_file, 'r') as copied_content:
            data = copied_content.read()
        copied_md5 = hashlib.md5(data).hexdigest()
        self.failif(self.stuff['cpfile_md5'] != copied_md5,
                    "Copied file '%s' does not match docker file "
                    "'%s'." % (copied_file, docker_file))
        self.loginfo("Copied file matches docker file.")

    def cleanup(self):
        if self.config['remove_after_test']:
            dkrcmd = DockerCmd(self, 'rm', [self.stuff['container_name']])
            dkrcmd.execute()
