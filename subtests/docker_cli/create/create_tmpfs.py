"""
Create container with --tmpfs option and inspect it
"""

from create import create_base
from dockertest.output import DockerVersion


class create_tmpfs(create_base):

    def initialize(self):
        super(create_tmpfs, self).initialize()
        # Minimum docker version 1.10 is required for --tmpfs
        DockerVersion().require_server("1.10")

    def run_once(self):
        super(create_tmpfs, self).run_once()
        cid = self.get_cid()
        self.sub_stuff['metadata'] = (
            self.sub_stuff['cont'].json_by_long_id(cid))

    def postprocess(self):
        super(create_tmpfs, self).postprocess()
        tmpfs_arg = self.config['tmpfs_arg']
        actual_tmpfs = self.sub_stuff['metadata'][0]['HostConfig']['Tmpfs']
        self.failif(tmpfs_arg not in actual_tmpfs,
                    "Container was not created with: --tmpfs %s"
                    % tmpfs_arg)
