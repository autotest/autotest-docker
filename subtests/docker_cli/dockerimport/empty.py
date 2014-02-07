"""
Sub-subtest module used by dockerimport test
"""

import os
from autotest.client import utils
from dockertest import output
from dockertest.subtest import SubSubtest

try:
    import docker
    DOCKERAPI = True
except ImportError:
    DOCKERAPI = False

class empty(SubSubtest):

    def run_once(self):
        super(empty, self).run_once()
        os.chdir(self.tmpdir)
        tar_command = self.config['tar_command']
        tar_options = self.config['tar_options']
        docker_command = self.test.config['docker_path']
        docker_options = self.test.config['docker_options']
        repo_name = self.make_repo_name()
        tar_command = "%s %s" % (tar_command, tar_options)
        dkr_command = ("%s %s import - %s" % (docker_command, docker_options,
                                              repo_name))
        self.run_tar(tar_command, dkr_command)

    def postprocess(self):
        super(empty, self).postprocess()
        # Don't assume 'repo_name_postfix' contains a tag
        repo_name = self.make_repo_name()
        # name parameter cannot contain tag
        self.config['repo'], self.config['tag'] = repo_name.split(':', 1)
        self.check_output()
        self.check_status()
        self.try_check_images()

    def cleanup(self):
        super(empty, self).cleanup()
        if DOCKERAPI and self.config.get('api_id') is not None:
            client = docker.Client()
            client.remove_image(self.config.get('api_id'))
        else:
            repo = self.config.get('repo')
            if repo is not None:
                docker_command = self.test.config['docker_path']
                docker_options = self.test.config['docker_options']
                command = ("%s %s rmi %s" % (docker_command, docker_options,
                                             self.config['repo']))
                utils.run(command)
            else:
                pass # Goal was repo removal

    def run_tar(self, tar_command, dkr_command):
        command = "%s | %s" % (tar_command, dkr_command)
        # Free, instance-specific namespace
        self.config['cmdresult'] = utils.run(command, ignore_status=True)

    def check_output(self):
        for out in (self.config['cmdresult'].stdout,
                    self.config['cmdresult'].stderr):
            output.usage_check(out)
            output.crash_check(out)

    def check_status(self):
        condition = self.config['cmdresult'].exit_status == 0
        self.test.failif(not condition, "Non-zero exit status")

    def try_check_images(self):
        # Simple presence check via docker API if available
        if DOCKERAPI:
            client = docker.Client()
            results = client.images(name=self.config['repo'])
            condition = len(results) == 1
            self.test.failif(not condition, "Imported repo. does not exist")
            repo = results[0]
            condition = str(repo['Repository']) == self.config['repo']
            self.test.failif(not condition, "Imported repo. name mismatch")
            condition = str(repo['Tag']) == self.config['tag']
            self.test.failif(not condition, "Imported repo. tag mismatch")
            # Used in removal if DOCKERAPI
            self.config['api_id'] = str(repo['Id'])
