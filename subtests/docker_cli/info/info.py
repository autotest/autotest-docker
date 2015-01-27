r"""
Summary
---------

Test output of docker info command and verifies it against
values obtained from userspace tools.

Operational Summary
----------------------

#. Run docker info command
#. Check output
#. Compare output with values obtained in userspace
#. Disk-size error-margins are large, sanity-check only.

Prerequisites
-------------------------------------

``dmsetup``, ``stat`` and ``du`` commands are available on host.
"""

from autotest.client import utils
from dockertest import subtest
from dockertest.output import OutputGood
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
import os


class info(subtest.Subtest):

    def run_once(self):
        super(info, self).run_once()
        # 1. Run with no options
        nfdc = DockerCmd(self, "info")
        self.stuff['cmdresult'] = mustpass(nfdc.execute())

    @staticmethod
    def _build_table(cli_output):
        out = cli_output.split('\n')
        out = [x.split(':', 1) for x in out if x]
        keys = [x[0].strip() for x in out]
        vals = [x[1].strip() for x in out]
        return dict(zip(keys, vals))

    def postprocess(self):
        # Raise exception on Go Panic or usage help message
        outputgood = OutputGood(self.stuff['cmdresult'])
        info_map = self._build_table(outputgood.stdout_strip)
        # verify each element
        self.verify_pool_name(info_map['Pool Name'])
        self.verify_sizes(info_map['Data loop file'],
                          info_map['Data Space Used'],
                          info_map['Data Space Total'],
                          info_map['Metadata loop file'],
                          info_map['Metadata Space Used'],
                          info_map['Metadata Space Total'])

    def verify_pool_name(self, docker_pool_name):
        read_pool_names = utils.run("dmsetup ls | grep 'docker.*pool'")
        raw_pools = read_pool_names.stdout.strip()
        pool_names = [x.split()[0] for x in raw_pools.split('\n')]

        # make sure there is only one pool
        self.failif(len(pool_names) != 1,
                    "There is more than one docker pool.")
        self.logdebug("One docker pool found.")

        read_pool_name = pool_names[0]
        # verify pool names
        self.logdebug("Read Pool Name: %s , Docker Pool Name: %s",
                      read_pool_name, docker_pool_name)
        self.failif(docker_pool_name != read_pool_name,
                    "Docker pool name does not mach dmsetup pool.")
        self.logdebug("Docker pool name matches dmsetup pool.")

    @staticmethod
    def size_bytes(num_str):
        num_str = num_str.lower()
        num, units = num_str.strip().split()
        if units == '':
            return float(num)  # bytes already
        if units == 'kb':
            return float(num) * 1024
        if units == 'mb':
            return float(num) * 1024 * 1024
        if units == 'gb':
            return float(num) * 1024 * 1024 * 1024
        if units == 'tb':
            return float(num) * 1024 * 1024 * 1024 * 1024

    def in_range(self, name, expected, reported):
        error = float(expected) * self.config['%s_error' % name]
        min_size = min([0.0, expected - error])
        max_size = expected + error
        msg = ("Docker info reported %s size %s, on disk size %s, "
               "acceptable range %s - %s"
               % (name, reported, expected, min_size, max_size))
        self.failif(reported > max_size, msg)
        self.failif(reported < min_size, msg)
        self.loginfo(msg)

    def verify_sizes(self, data_file, data_used, data_total,
                     meta_file, meta_used, meta_total):
        # Convert reported sizes into bytes
        data_used = self.size_bytes(data_used)
        data_total = self.size_bytes(data_total)
        meta_used = self.size_bytes(meta_used)
        meta_total = self.size_bytes(meta_total)

        # read sizes of the data and meta files from disk
        read_size = lambda x: float(
            utils.run("du --block-size=1 %s | cut -f1" % x).stdout.strip())

        read_data_used = float(read_size(data_file))
        read_data_total = float(os.stat(data_file).st_size)
        read_meta_used = float(read_size(meta_file))
        read_meta_total = float(os.stat(meta_file).st_size)

        self.in_range('data', read_data_used, data_used)
        self.in_range('data_total', read_data_total, data_total)
        self.in_range('meta', read_meta_used, meta_used)
        self.in_range('meta_total', read_meta_total, meta_total)
        # Make sure used < total (idiot check)
        self.failif(read_data_used >= read_data_total,
                    "Data used > Data total")
        self.failif(read_meta_used >= read_meta_total,
                    "Meta used > Meta total")
