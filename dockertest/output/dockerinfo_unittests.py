#!/usr/bin/env python

import os
import sys
import types
from unittest2 import TestCase, main

# DO NOT allow this function to get loose in the wild!
def mock(mod_path):
    """
    Recursively inject tree of mocked modules from entire mod_path
    """
    name_list = mod_path.split('.')
    child_name = name_list.pop()
    child_mod = sys.modules.get(mod_path, types.ModuleType(child_name))
    if len(name_list) == 0:  # child_name is left-most basic module
        if child_name not in sys.modules:
            sys.modules[child_name] = child_mod
        return sys.modules[child_name]
    else:
        # New or existing child becomes parent
        recurse_path = ".".join(name_list)
        parent_mod = mock(recurse_path)
        if not hasattr(sys.modules[recurse_path], child_name):
            setattr(parent_mod, child_name, child_mod)
            # full-name also points at child module
            sys.modules[mod_path] = child_mod
        return sys.modules[mod_path]

setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.utils'), 'PlaceHolder', Exception)


class TestDockerInfo(TestCase):

    def setUp(self):
        from dockertest.output import DockerInfo
        self.DockerInfo = DockerInfo

    def tearDown(self):
        del self.DockerInfo

    def test_basic(self):
        info_string = """Containers: 0
 Running: 0
 Paused: 0
 Stopped: 0
Images: 3
Server Version: 1.12.6
Storage Driver: devicemapper
 Pool Name: vg--docker-docker--pool
 Pool Blocksize: 524.3 kB
 Data file: %s
 Library Version: 1.02.135-RHEL7 (2016-11-16)
Logging Driver: journald
Plugins:
 Volume: local lvm
 Network: host null bridge overlay
ID: 5UCC:ANAG:4BIE:2KK6:VGP4:XKVO:5HB5:RPOA:PFLJ:HXRF:FCDV
Insecure Registries:
 127.0.0.0/8""" % ''

        actual = self.DockerInfo(info_string)

        # How we expect _build_table() to parse that.
        expect = {
            'containers': '0',
            'containers...': {
                'running': '0',
                'paused': '0',
                'stopped': '0',
            },
            'images': '3',
            'server_version': '1.12.6',
            'storage_driver': 'devicemapper',
            'storage_driver...': {
                'pool_name': 'vg--docker-docker--pool',
                'pool_blocksize': '524.3 kB',
                'data_file': '',
                'library_version': '1.02.135-RHEL7 (2016-11-16)',
            },
            'logging_driver': 'journald',
            'plugins': '',
            'plugins...': {
                'volume': 'local lvm',
                'network': 'host null bridge overlay',
            },
            'id': '5UCC:ANAG:4BIE:2KK6:VGP4:XKVO:5HB5:RPOA:PFLJ:HXRF:FCDV',
            'insecure_registries': '',
            'insecure_registries...': {
                '127.0.0.0/8': '',
            }
        }

        # If test fails, report full (unabbreviated) diffs.
        self.maxDiff = None

        # Relies on knowledge of class internals (.info_table). This is OK
        # for a unit test; not OK for general use.
        self.assertEqual(actual.info_table, expect,
                         "parsed output from docker info")

        # The common case: fetch the simple value of a key
        self.assertEqual(actual.get('server_version'), '1.12.6',
                         'string accessor, pre-normalized key')
        self.assertEqual(actual.get('Server Version'), '1.12.6',
                         'string accessor, non-normalized key')

        # Fetch nested elements
        self.assertEqual(actual.get('containers', {}), expect['containers...'],
                         'subelement accessor: as dict')
        self.assertEqual(actual.get('containers', 'paused'),
                         expect['containers...']['paused'],
                         'subelement accessor: single element')

        # reproducer
        self.assertEqual(str(actual), 'DockerInfo("%s")' % info_string,
                         "string reproducer")


if __name__ == '__main__':
    main()
