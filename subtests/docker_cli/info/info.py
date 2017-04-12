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
from dockertest.output import OutputGood
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.images import DockerImages
from dockertest.xceptions import DockerTestFail


class info(subtest.Subtest):

    def run_once(self):
        super(info, self).run_once()
        # 1. Run with no options
        nfdc = DockerCmd(self, "info")
        self.stuff['cmdresult'] = mustpass(nfdc.execute())

    @staticmethod
    def _build_table(cli_output):
        """
        'docker info' returns a human-readable list of key: value pairs.
        Some are indented by a space, indicating that these key/values
        are subelements of a previous element. To wit:

             Images: 3
             Server Version: 1.12.6
             Storage Driver: devicemapper
              Pool Name: vg--docker-docker--pool
              Pool Blocksize: 524.3 kB
              ...
             Logging Driver: journald

        In this case 'Images', 'Server Version', and 'Logging Driver'
        are simple tuples but 'Storage Driver' has both a value and
        a set of further key/value pairs: Pool Name, Pool Blocksize, ...

        We parse that and return a dict with the expected key/value
        mapping *and* an extra: for all elements with subelements,
        'element...' (element name plus three dots) is a dict containing
        the subelements. E.g. x['Storage Driver...']['Pool Name'] = 'vg--etc'
        """
        out = {}
        current_key = None
        for line in cli_output.splitlines():
            # Almost every line will be Foo: Bar, but 'Insecure Registries:'
            # is followed by a simple list of IPv4 netmasks
            if ': ' in line or line.endswith(':'):
                (key, value) = [e.strip() for e in line.split(':', 1)]
            else:
                key = line.strip()
                value = ''
            if line.startswith(' '):
                if not current_key:
                    raise IndexError("Internal error: indented output line"
                                     " '%s' from docker info with no previous"
                                     " unindented lines.", line)
                if current_key not in out:
                    out[current_key] = {}
                out[current_key][key] = value
            else:
                out[key] = value
                current_key = key + '...'
        return out

    def postprocess(self):
        # Raise exception on Go Panic or usage help message
        outputgood = OutputGood(self.stuff['cmdresult'])
        info_map = self._build_table(outputgood.stdout_strip)

        # We support multiple storage drivers. Each one has a different
        # set of key/value settings under 'info'; so each one has a
        # dedicated helper method for validating.
        storage_driver = info_map['Storage Driver'].lower()
        try:
            handler = '_postprocess_' + storage_driver
            getattr(self, handler)(info_map['Storage Driver...'])
        except AttributeError:
            raise DockerTestFail("Unknown storage driver: %s" % storage_driver)
        except KeyError:
            raise DockerTestFail("Unexpected output from docker info:"
                                 " 'Storage Driver' section has no"
                                 " additional info elements.")

        # Count 'docker images', compare to the 'Images' info key.
        # Yes, that's unreliable on a busy system. We're not on a busy system.
        di = DockerImages(self)
        di.images_args = "%s --all" % di.images_args
        img_set = set(di.list_imgs_ids())  # don't count multi-tags
        img_cnt = int(info_map['Images'])
        self.failif_ne(len(img_set), img_cnt,
                       "count of 'docker images' vs 'docker info'->Images")

    def _postprocess_devicemapper(self, info_map):
        """
        Verify docker info settings for devicemapper storage driver.
        """
        self.failif_ne(info_map['Data file'].lower(), '',
                       'Data file')
        self.failif_ne(info_map['Metadata file'].lower(), '',
                       'Metadata file')

        # verify value of elements
        self.verify_pool_name(info_map['Pool Name'])
        data_name = 'Data loop file'
        metadata_name = 'Metadata loop file'
        if data_name in info_map:
            self.verify_sizes(info_map[data_name],
                              info_map['Data Space Used'],
                              info_map['Data Space Total'],
                              info_map[metadata_name],
                              info_map['Metadata Space Used'],
                              info_map['Metadata Space Total'])
        else:
            data_name = 'Data file'
            metadata_name = 'Metadata file'
            # TODO: Checks based oninfo_map['Backing Filesystem:']

    def _postprocess_overlay2(self, info_map):
        """
        Verify docker info settings for overlay2 storage driver.
        """
        self.failif_ne(info_map['Backing Filesystem'], 'xfs',
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
