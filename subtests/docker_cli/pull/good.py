"""
Test output of docker Pull command

docker pull full_name

1. Try to download repository from registry
2. Check if image is in local repository.
3. Remote image from local repository
"""

from pull import pull_base, check_registry

class good(pull_base):
    config_section = 'docker_cli/pull/good'

    def setup(self):
        # check docker registry:
        registry_addr = self.config["docker_registry_host"]
        check_registry(registry_addr)
