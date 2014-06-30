"""
Test output of the docker insert command

1. Insert file from URL into a docker image using docker insert
2. Make sure the file was successfully inserted by comparing the
   inserted file and the url.
"""

from autotest.client import utils
from dockertest import subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.images import DockerImage
from dockertest.xceptions import DockerTestNAError
import hashlib
import urllib2

class insert(subtest.Subtest):
    config_section = 'docker_cli/insert'

    def initialize(self):
        super(insert, self).initialize()
        self.stuff['cntr_objs'] = []
        #check for a valid url for the test
        file_url = self.config['file_url']
        if not file_url or len(file_url) < 4:
            raise DockerTestNAError("'file_url' in insert.ini not set.")
        #pull down file at url for use later
        response = urllib2.urlopen(file_url)
        contents = response.read()
        self.stuff['contents'] = contents

    def run_once(self):
        super(insert, self).run_once()
        fin = DockerImage.full_name_from_defaults(self.config)
        file_path = "/tmp/" + utils.generate_random_string(8)
        self.stuff['file_path'] = file_path
        subargs = [fin,
                   self.config['file_url'],
                   file_path]
        nfdc = NoFailDockerCmd(self, "insert", subargs,
                               timeout=self.config['docker_timeout'])
        cmdresult = nfdc.execute()
        inserted_image = cmdresult.stdout.split()[-1].strip()
        self.stuff['inserted_image'] = inserted_image

    def postprocess(self):
        super(insert, self).postprocess()
        source_md5 = hashlib.md5(self.stuff['contents']).hexdigest()
        docker_md5 = self._get_docker_md5(self.stuff['inserted_image'],
                                          self.stuff['file_path'],)
        self.failif(docker_md5 != source_md5,
                    "Url file does not match inserted file "
                    "'%s'." % (self.stuff['file_path']))
        self.loginfo("Source file matches inserted file.")

    def _get_docker_md5(self, image_id, insert_path):
        subargs = ['--rm',
                   image_id,
                   '/bin/bash',
                   '-c',
                   '"md5sum ' + insert_path + '"']
        dkrcmd = DockerCmd(self, 'run', subargs)
        cmdresult = dkrcmd.execute()
        return cmdresult.stdout.split()[0]

    def cleanup(self):
        super(insert, self).cleanup()
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            try:
                cl = dc.list_container_ids()
            except ValueError:
                pass
            else:
                dkrcmd = DockerCmd(self, 'kill', cl)
                dkrcmd.execute()
                dkrcmd = DockerCmd(self, 'rm', cl)
                dkrcmd.execute()
            dkrcmd = DockerCmd(self, 'rmi', ['--force',
                                             self.stuff['inserted_image']])
            dkrcmd.execute()
