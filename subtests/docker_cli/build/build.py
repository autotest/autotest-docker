"""
Test run of docker build command

1. Change to 'build_root' directory
2. Run docker build
3. Check for completed image
4. Remove image, change back to previous dir.
"""

import os, os.path
from autotest.client import utils
from dockertest import subtest, output

try:
    import docker
    import docker.client
    DOCKERAPI = True
except ImportError:
    DOCKERAPI = False

class build(subtest.Subtest):
    version = "0.0.1"
    config_section = 'docker_cli/build'

    def initialize(self):
        super(build, self).initialize()
        # local copy, safe to stick temporary stuff here
        self.config['before_chdir'] = os.getcwd()
        dockerfile = os.path.join(self.config['docker_build_path_or_uri'],
                                  'Dockerfile')
        if not os.path.isfile(dockerfile):
            self.logwarning("Not a file: %s", dockerfile)
        condition = self.config['build_timeout_seconds'] >= 10
        self.failif(not condition, "Config option build_timeout_seconds "
                                   "is probably too short")

    def run_once(self):
        super(build, self).run_once()
        self.config['repo_name'] = ("%s%s%s" % (self.config['repo_name_prefix'],
                                    utils.generate_random_string(4),
                                    self.config['repo_name_postfix']))
        self.config['docker_build_options'] += " -t " + self.config['repo_name']
        dockercmd = ("%s %s build %s %s"
                     % (self.config['docker_path'],
                        self.config['docker_options'],
                        self.config['docker_build_options'],
                        self.config['docker_build_path_or_uri']))
        self.loginfo("Executing background command: %s" % dockercmd)
        self.config["async_job"] = utils.AsyncJob(dockercmd)
        self.loginfo("Running, could take upto %d seconds to complete",
                     self.config['build_timeout_seconds'])
        self.config["async_job"].wait_for(self.config['build_timeout_seconds'])

    def postprocess(self):
        super(build, self).postprocess()
        condition = self.config["async_job"].result.exit_status == 0
        self.failif(not condition, "Non-zero build exit status")
        self.loginfo("Exit code: %s, checking output...",
                     self.config["async_job"].result.exit_status)
        self._check_output()
        self._try_check_existance()

    def cleanup(self):
        super(build, self).cleanup()
        if self.config['try_remove_after_test']:
            self._try_repo_remove()
        os.chdir(self.config['before_chdir'])

    def _check_output(self):
        stdout = self.config["async_job"].get_stdout()
        stderr = self.config["async_job"].get_stderr()
        output.crash_check(stdout)
        output.crash_check(stderr)
        output.usage_check(stdout)
        output.usage_check(stderr)

    def _try_check_existance(self):
        if not DOCKERAPI:
            return
        # This dictionary/namespace is more private to this test
        self.config['api_client'] = docker.Client()
        # name parameter cannot contain tag
        repo_name = self.config['repo_name'].split(':', 1)[0]
        # search result list
        repo = self.config['api_client'].images(name=repo_name)
        condition = len(repo) == 1
        self.failif(not condition, "Built repository not found")
        self.config['api_repo'] = repo[0]

    def _try_repo_remove(self):
        success = False
        if DOCKERAPI:
            try:
                _id = self.config['api_repo']['Id']
                self.config['api_client'].remove_image(_id)
                success = True
            except docker.client.APIError, detail:
                self.logdebug("docker.client.APIError: %s", detail)
                success = False
        else:
            command = ("%s rmi %s" % (self.config['docker_path'],
                                      self.config['repo_name']))
            cmdresult = utils.run(command, ignore_status=True)
            if cmdresult.exit_status == 0:
                success = True
            else:
                success = False
        if success:
            self.loginfo("Successfully removed test image")
        else:
            self.loginfo("Could not remove test image (see debug log for info)")
