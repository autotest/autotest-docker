"""
Test output of docker Pull command

docker pull --tag=xxx full_name

1. Try to download repository from registry
2. Check if image is in local repository.
3. Remote image from local repository
"""
# distutils.version is incorrectly missing in Travis CI, disable warning
from distutils.version import LooseVersion  # pylint: disable=E0611
from pull import pull_base, check_registry
from dockertest.images import DockerImage
from dockertest.output import mustpass
from dockertest.dockercmd import DockerCmd
from dockertest.output import DockerVersion
from dockertest.xceptions import DockerTestNAError


class good_extra_tag(pull_base):
    max_version = "0.11.1-dev"  # Skip test after this docker version

    def setup(self):
        # check docker registry:
        registry_addr = self.config["docker_registry_host"]
        check_registry(registry_addr)

    def initialize(self):
        super(good_extra_tag, self).initialize()
        ver_stdout = mustpass(DockerCmd(self, "version").execute()).stdout
        dv = DockerVersion(ver_stdout)
        client_version = LooseVersion(dv.client)
        max_version = LooseVersion(self.max_version)
        if client_version > max_version:
            raise DockerTestNAError("Not testing deprecated --tag option")

    def complete_docker_command_line(self):
        super(good_extra_tag, self).complete_docker_command_line()
        config_copy = self.config.copy()
        # Remove tag from config
        docker_repo_tag = config_copy.pop('docker_repo_tag')
        full_name_wo_tag = DockerImage.full_name_from_defaults(config_copy)
        return ["--tag=%s" % (docker_repo_tag), full_name_wo_tag]
