"""
Sub-subtest module used by dockerimport test
"""

import os, logging
from autotest.client import utils
from dockertest import output
from dockertest.subtest import SubSubtest
from dockertest.dockercmd import DockerCmd

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
                DockerCmd(self.test, 'rmi', self.config['result_id'])
            else:
                pass # Goal was repo removal

    def run_tar(self, tar_command, dkr_command):
        command = "%s | %s" % (tar_command, dkr_command)
        # Free, instance-specific namespace
        cmdresult = utils.run(command, ignore_status=True)
        self.config['cmdresult'] = cmdresult
        self.loginfo("Command result: %s", cmdresult)
        self.config['result_id'] = cmdresult.stdout.strip()

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
        api_id = None
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
            api_id = repo.get('Id')
            if api_id is None:
                logging.error("Could not retrieve repo %s's Id using "
                              "docker python API.  Data returned: '%s'",
                              self.config['repo'], str(repo))
            else:
                self.loginfo("Found Id %s with docker python API", api_id)
        if api_id is None:
            # fail -> raise exception
            cmdresult = DockerCmd(self.test, 'images', '--quiet',
                                  self.config['repo'])
            api_id = cmdresult.stdout.strip()
            self.loginfo("Found Id %s with docker command", api_id)
        # Mimic behavior of throwing away all but first 12 characters of Id
        result_id = self.config['result_id']
        result_id = result_id[0:12]
        self.config['api_id'] = api_id  #  used in cleanup()
        condition = str(result_id) == str(api_id)
        self.test.failif(not condition, "Repository Id's do not match (%s,%s)"
                         % (result_id, api_id))
