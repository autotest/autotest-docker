"""
Test read access to a file shared by volume
"""

import re
from dockertest.xceptions import DockerTestNAError
from dockertest.output import OutputGood
from run_volumes import volumes_base
from run_volumes import DockerTestNAError


class file_volume(volumes_base):

    @staticmethod
    def make_test_files(host_path):
        # Not used in this test
        del host_path
        return (None, None, None, None)

    @staticmethod
    def make_test_dict(read_fn, write_fn, read_data, read_hash,
                       host_path, cntr_path):
        # not used in this test
        del read_fn
        del write_fn
        del read_data
        del read_hash
        return {'host_path': host_path, 'cntr_path': cntr_path}

    def init_paths(self):
        host_paths, cntr_paths = super(file_volume, self).init_paths()
        if len(host_paths) != 1:
            raise DockerTestNAError("Only one host_paths item is supported")
        if len(cntr_paths) != 1:
            raise DockerTestNAError("Only one cntr_paths item is supported")
        return host_paths, cntr_paths

    def run_once(self):
        super(file_volume, self).run_once()
        dockercmd = self.sub_stuff['dockercmds'][0]
        self.sub_stuff['cmdresults'].append(dockercmd.execute())

    def postprocess(self):
        super(file_volume, self).postprocess()
        cmdresult = self.sub_stuff['cmdresults'][0]
        OutputGood(cmdresult)
        regex = re.compile(self.config['regex'])
        self.failif(not regex.search(cmdresult.stdout),
                    "Fail match regex '%s' to: '%s'"
                    % (regex.pattern, cmdresult.stdout))
