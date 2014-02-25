"""
Test output of docker version command

1. Run with no options
2. Run with valid option
3. Run with invalid option
4. Run with empty option
"""

from dockertest import subtest, output
from dockertest.dockercmd import DockerCmd, NoFailDockerCmd

try:
    from docker.client import Client
    DOCKERAPI = True
except ImportError:
    DOCKERAPI = False

class version(subtest.Subtest):
    version = "0.0.1"
    config_section = 'docker_cli/version'

    def initialize(self):
        super(version, self).initialize()

    def run_once(self):
        super(version, self).run_once()
        # 1. Run with no options
        self.config['cmdresult1'] = NoFailDockerCmd(self, "version")
        # 2. Run with valid option
        self.config['cmdresult2'] = NoFailDockerCmd(self,
                                                    self.config['valid_option'],
                                                    'version')
        # 3. Run with invalid option
        self.config['cmdresult3'] = DockerCmd(self,
                                              self.config['invalid_option'],
                                              'version')
        # 4. Run with empty option
        self.config['cmdresult4'] = DockerCmd(self, '" "', 'version')

    def postprocess(self):

        self.failif(self.config['cmdresult1'].exit_status != 0,
                    "cmdresult1 non-zero exit code")
        version_string = self.config['cmdresult1'].stdout.strip()
        docker_version = output.DockerVersion(version_string)
        self.loginfo("Found docker versions client: %s server %s ",
                     docker_version.client, docker_version.server)
        self.try_verify_version(docker_version)
        # TODO: More comprehensive checks
        msg1 = "Non-zero command exit status"
        msg2 = "Unexpected 0 exit status"
        self.failif(self.config['cmdresult2'].exit_status != 0, msg1)
        self.failif(self.config['cmdresult3'].exit_status == 0, msg2)
        self.failif(self.config['cmdresult4'].exit_status == 0, msg2)

    def try_verify_version(self, docker_version):
        if not DOCKERAPI:
            return
        client = Client()
        client_version = client.version()
        self.failif(client_version['Version'] != docker_version.client,
                    "Docker cli version does not match docker client API "
                    "version")
        self.loginfo("Docker cli version matches docker client API version")
