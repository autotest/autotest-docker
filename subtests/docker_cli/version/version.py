r"""
Summary
---------

Test output of docker version command

Operational Summary
----------------------

#. Run docker version command
#. Check output
#. compare to daemon API version

Prerequisites
---------------

None
"""

from dockertest import subtest
from dockertest.output import OutputGood
from dockertest.output import DockerVersion
from dockertest.output import mustpass
from dockertest.dockercmd import DockerCmd
from dockertest.docker_daemon import SocketClient


class version(subtest.Subtest):

    def initialize(self):
        super(version, self).initialize()

    def run_once(self):
        super(version, self).run_once()
        # 1. Run with no options
        nfdc = DockerCmd(self, "version")
        self.stuff['cmdresult'] = mustpass(nfdc.execute())

    def postprocess(self):
        super(version, self).postprocess()
        # Raise exception on Go Panic or usage help message
        outputgood = OutputGood(self.stuff['cmdresult'])
        docker_version = DockerVersion(outputgood.stdout_strip)
        self.loginfo("docker version client: %s server %s",
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
