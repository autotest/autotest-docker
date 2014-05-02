"""
Test output of docker inspect command

1. Create some docker containers
2. Run docker inspect command on them
3. Check output
4. Compare output with values obtained in the container's config
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest.dockercmd import NoFailDockerCmd
from dockerinspect import inspect_base

class inspect_all(inspect_base):

    def initialize(self):
        super(inspect_all, self).initialize()
        self.sub_stuff['name'] = self.create_simple_container(self)

    def run_once(self):
        super(inspect_all, self).run_once()
        # find inputs to this
        subargs = [self.sub_stuff['name']]
        nfdc = NoFailDockerCmd(self.parent_subtest, "inspect", subargs)
        self.sub_stuff['cmdresult'] = nfdc.execute()

    def postprocess(self):
        super(inspect_all, self).postprocess()
        cli_output = self.parse_cli_output(self.sub_stuff['cmdresult'].stdout)
        cid = self.get_cid_from_name(self, self.sub_stuff['name'])
        config_map = self.get_config_maps([cid])
        ifields = self.config['ignore_fields'].split(',')
        self.verify_same_configs(self,
                                 config_map,
                                 cli_output,
                                 ignore_fields=ifields)

