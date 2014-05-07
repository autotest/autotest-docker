"""
Test output of docker info command

1. Run docker info command
2. Check output
3. Compare output with values obtained in userspace
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from autotest.client import utils
from dockertest import subtest
from dockertest.output import OutputGood
from dockertest.dockercmd import NoFailDockerCmd
import os

class info(subtest.Subtest):

    def run_once(self):
        super(info, self).run_once()
        # 1. Run with no options
        nfdc = NoFailDockerCmd(self, "info")
        self.stuff['cmdresult'] = nfdc.execute()

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
        #verify each element
        self.verify_pool_name(info_map['Pool Name'])
        self.verify_sizes(info_map['Data file'],
                         info_map['Data Space Used'],
                         info_map['Data Space Total'],
                         info_map['Metadata file'],
                         info_map['Metadata Space Used'],
                         info_map['Metadata Space Total'])

    def verify_pool_name(self, docker_pool_name):
        read_pool_names = utils.run("dmsetup ls | grep 'docker.*pool'")
        raw_pools = read_pool_names.stdout.strip()
        pool_names = [x.split()[0] for x in raw_pools.split('\n')]

        #make sure there is only one pool
        self.failif(len(pool_names) != 1,
                    "There is more than one docker pool.")
        self.logdebug("One docker pool found.")

        read_pool_name = pool_names[0]
        #verify pool names
        self.logdebug("Read Pool Name: %s , Docker Pool Name: %s",
                      read_pool_name, docker_pool_name)
        self.failif(docker_pool_name != read_pool_name,
                    "Docker pool name does not mach dmsetup pool.")
        self.logdebug("Docker pool name matches dmsetup pool.")

    @staticmethod
    def _sizeof_fmt_mb(num, input_unit='b'):
        conv = float(1024*1024)
        if input_unit == 'Kb':
            conv = float(1024)
        fmt_num = num / conv
        return "%.1f Mb" % (fmt_num)

    def verify_sizes(self, data_file, data_used, data_total,
                     meta_file, meta_used, meta_total):
        #read sizes of the data and meta files
        read_size = lambda x: float(
                                utils.run("du %s | cut -f1" % x
                                            ).stdout.strip())
        read_data_size = read_size(data_file)
        read_meta_size = read_size(meta_file)
        #read apparent sizes of data and meta files
        data_asize = os.stat(data_file).st_size
        meta_asize = os.stat(meta_file).st_size
        #format sizes to compare them to docker output
        read_data_size_mb = self._sizeof_fmt_mb(read_data_size, 'Kb')
        read_meta_size_mb = self._sizeof_fmt_mb(read_meta_size, 'Kb')
        read_data_asize_mb = self._sizeof_fmt_mb(data_asize)
        read_meta_asize_mb = self._sizeof_fmt_mb(meta_asize)

        #compare actual file sizes
        self.logdebug("Read metadata file size total: %s, Docker metadata file "
                     "total size: %s", read_meta_asize_mb, meta_total)
        self.failif(meta_total != read_meta_asize_mb,
                    "Docker reported metadata file size total does not match "
                    "read file size total.")
        self.logdebug("Docker reported metadata file size total matches read "
                     "file size total.")
        self.logdebug("Read data file size total: %s, Docker data file total "
                     "size: %s", read_data_asize_mb, data_total)
        self.failif(data_total != read_data_asize_mb,
                    "Docker reported data file size total does not match read "
                    "file size total.")
        self.logdebug("Docker reported data file size total matches read file "
                     "size total.")

        #compare real used file sizes
        self.logdebug("Read metadata file size: %s, Docker metadata file size: "
                     "%s", read_meta_size_mb, meta_used)
        self.failif(meta_used != read_meta_size_mb,
                    "Docker reported metadata file size does not match read "
                    "file size.")
        self.logdebug("Docker reported metadata file size matches read file "
                     "size.")
        self.logdebug("Read data file size: %s, Docker data file size: %s",
                     read_data_size_mb, data_used)
        self.failif(data_used != read_data_size_mb,
                    "Docker reported data file size does not match read file "
                    "size.")
        self.logdebug("Docker reported data file size matches read file size.")
