"""
Test output of docker inspect command

1. Create some docker containers
2. Run docker inspect command on them
3. Check that all keys are CamelCase
4. Check output
5. Compare output with values obtained in the container's config
"""

import re

from dockerinspect import inspect_base
from dockertest.output import mustpass
from dockertest.dockercmd import DockerCmd


class inspect_all(inspect_base):

    re_camel_case = re.compile(r'^[A-Z][a-zA-Z]*$')

    def initialize(self):
        super(inspect_all, self).initialize()
        self.sub_stuff['name'] = self.create_simple_container(self)

    def run_once(self):
        super(inspect_all, self).run_once()
        # find inputs to this
        subargs = [self.sub_stuff['name']]
        nfdc = DockerCmd(self, "inspect", subargs)
        self.sub_stuff['cmdresult'] = mustpass(nfdc.execute())

    def postprocess(self):
        super(inspect_all, self).postprocess()
        cli_output = self.parse_cli_output(self.sub_stuff['cmdresult'].stdout)
        self.check_camel_case(cli_output)
        cid = self.get_cid_from_name(self, self.sub_stuff['name'])
        config_map = self.get_config_maps([cid])
        # https://bugzilla.redhat.com/show_bug.cgi?id=1092781
        ifields = self.config['ignore_fields'].split(',')
        self.verify_same_configs(self,
                                 config_map,
                                 cli_output,
                                 ignore_fields=ifields)

    def check_camel_case(self, info):
        try:
            self._check_camel_case(info)
            self.loginfo("CamelCase test PASSED")
        except ValueError, details:
            self.failif(True, "%s\n%s" % (details, info))

    def _check_camel_case(self, info):
        if isinstance(info, list):
            for item in info:
                self._check_camel_case(item)
        elif isinstance(info, dict):
            for key, value in info.iteritems():
                if not self.re_camel_case.match(key):
                    raise ValueError("Key '%s' is not CamelCase" % key)
                self._check_camel_case(value)
