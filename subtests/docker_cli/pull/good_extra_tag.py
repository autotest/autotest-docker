"""
Test output of docker Pull command

docker pull --tag=xxx full_name

1. Try to download repository from registry
2. Check if image is in local repository.
3. Remote image from local repository
"""
from pull import pull_base, check_registry
from dockertest.images import DockerImage

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


class good_extra_tag(pull_base):
    config_section = 'docker_cli/pull/good_extra_tag'

    def setup(self):
        # check docker registry:
        registry_addr = self.config["docker_registry_host"]
        check_registry(registry_addr)

    def complete_docker_command_line(self):
        super(good_extra_tag, self).complete_docker_command_line()
        config_copy = self.config.copy()
        # Remove tag from config
        docker_repo_tag = config_copy.pop('docker_repo_tag')
        full_name_wo_tag = DockerImage.full_name_from_defaults(config_copy)
        return ["--tag=%s" % (docker_repo_tag), full_name_wo_tag]
