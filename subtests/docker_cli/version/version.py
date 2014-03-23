"""
Test output of docker version command

1. Run docker version command
2. Check output
3. compare to daemon API version
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest import subtest
from dockertest.output import OutputGood
from dockertest.output import DockerVersion
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.docker_daemon import SocketClient


class version(subtest.Subtest):

    def initialize(self):
        super(version, self).initialize()

    def run_once(self):
        super(version, self).run_once()
        # 1. Run with no options
        nfdc = NoFailDockerCmd(self, "version")
        self.stuff['cmdresult'] = nfdc.execute()

    def postprocess(self):
        # Raise exception on Go Panic or usage help message
        outputgood = OutputGood(self.stuff['cmdresult'])
        docker_version = DockerVersion(outputgood.stdout_strip)
        self.loginfo("Found docker versions client: %s server %s ",
                     docker_version.client, docker_version.server)
        self.verify_version(docker_version)

    def verify_version(self, docker_version):
        # TODO: Make URL to daemon configurable
        client = SocketClient()
        _version = client.version()
        client_version = _version['Version']
        self.failif(client_version != docker_version.client,
                    "Docker cli version %s does not match docker client API "
                    "version %s" % (client_version, docker_version.client))
        self.loginfo("Docker cli version matches docker client API version")
