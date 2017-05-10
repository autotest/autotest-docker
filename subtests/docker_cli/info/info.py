r"""
Summary
---------

Test output of docker info command and verifies it against
values obtained from userspace tools.  Currently only supports
loop-back files for comparing on-disk size. Other setups
just check pool name.

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

import os
from autotest.client import utils
from dockertest import subtest
from dockertest.output import DockerInfo
from dockertest.images import DockerImages
from dockertest.xceptions import DockerTestFail


class info(subtest.Subtest):

    def run_once(self):
        super(info, self).run_once()
        self.stuff['dockerinfo'] = DockerInfo()

    def postprocess(self):
        super(info, self).postprocess()
        info_table = self.stuff['dockerinfo']

        # We support multiple storage drivers. Each one has a different
        # set of key/value settings under 'info'; so each one has a
        # dedicated helper method for validating.
        driver_name = info_table.get('storage_driver')
        self.failif(not driver_name, "'docker info' did not return"
                                     " a value for 'Storage Driver'")
        self.loginfo("Storage Driver = %s", driver_name)
        try:
            handler = getattr(self, '_postprocess_' + driver_name.lower())
        except AttributeError:
            raise DockerTestFail("Unknown storage driver: %s" % driver_name)
        handler(info_table.get('storage_driver', {}))

        # Count 'docker images', compare to the 'Images' info key.
        # Yes, that's unreliable on a busy system. We're not on a busy system.
        di = DockerImages(self)
        di.images_args = "%s --all" % di.images_args
        img_set = set(di.list_imgs_ids())  # don't count multi-tags
        img_cnt = int(info_table.get('images'))
        self.failif_ne(len(img_set), img_cnt,
                       "count of 'docker images' vs 'docker info'->Images")

    def _postprocess_devicemapper(self, info_map):
        """
        Verify docker info settings for devicemapper storage driver.
        """
        self.failif_ne(info_map['data_file'].lower(), '',
                       'Data file')
        self.failif_ne(info_map['metadata_file'].lower(), '',
                       'Metadata file')

        # verify value of elements
        self.verify_pool_name(info_map['pool_name'])
        data_name = 'data_loop_file'
        metadata_name = 'metadata_loop_file'
        if data_name in info_map:
            self.verify_sizes(info_map[data_name],
                              info_map['data_space_used'],
                              info_map['data_space_total'],
                              info_map[metadata_name],
                              info_map['metadata_space_used'],
                              info_map['metadata_space_total'])
        else:
            data_name = 'data_file'
            metadata_name = 'metadata_file'
            # TODO: Checks based oninfo_map['Backing Filesystem:']

    def _postprocess_overlay2(self, info_map):
        """
        Verify docker info settings for overlay2 storage driver.
        """
        self.failif_ne(info_map['backing_filesystem'], 'xfs',
                       'overlay2 Backing Filesystem')

    def verify_pool_name(self, expected_pool_name):
        """
        Pool Name reported by docker info should be listed in
        results from dmsetup ls.
        """
        read_pool_names = utils.run("dmsetup ls")
        raw_pools = read_pool_names.stdout.strip()
        pool_names = [x.split()[0] for x in raw_pools.split('\n')
                      if 'pool' in x]

        # make sure there is at least one pool
        self.failif(len(pool_names) < 1,
                    "'dmsetup ls' reports no docker pools.")
        self.logdebug("Docker pool(s) found: %s" % pool_names)

        # verify pool names
        self.failif(expected_pool_name not in pool_names,
                    "Docker info pool name '%s' (from docker info)"
                    " not found in dmsetup ls list '%s'" %
                    (expected_pool_name, pool_names))
        self.logdebug("Docker pool name found in dmsetup ls.")

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
        min_size = max([0.0, expected - error])
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
