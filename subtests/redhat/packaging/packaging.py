r"""
Summary
-------

Meta-tests: docker packaging, installation, setup. Nothing here
actually runs docker.

Operational Summary
-------------------

#. Run 'file' against docker binaries, make sure output includes 'not stripped'
"""

import os
import magic
from dockertest import subtest
from dockertest.subtest import SubSubtest


class packaging(subtest.SubSubtestCaller):

    """ SubSubtest caller """


class packaging_base(SubSubtest):
    pass


class debuginfo_present(packaging_base):
    """
    bz1280068 - make sure docker binary is shipped with debug info.
    We simply use libmagic to check for us. Note that this may fail
    if/when it becomes possible to ship debuginfo as a separate rpm.
    """

    def initialize(self):
        super(debuginfo_present, self).initialize()
        # The python-magic package that ships with RHEL is clunky, obsolete,
        # undocumented, and bears no relation to any currently known magic.py
        # in other distros or via pip. Refer to:
        #     https://stackoverflow.com/questions/25286176
        self.sub_stuff['magic'] = magic.open(magic.MAGIC_NONE)
        self.sub_stuff['magic'].load()

    def run_once(self):
        super(debuginfo_present, self).run_once()
        # Another way to search for DWARF might be:
        #    readelf -S /usr/bin/docker-current |grep -i debug_info
        for binfile in ['docker-current', 'docker-latest']:
            path = os.path.join('/usr/bin', binfile)
            if os.path.exists(path):
                filetype = self.sub_stuff['magic'].file(path)
                self.failif_not_in('not stripped', filetype,
                                   '%s binary is stripped of debuginfo' % path)

    def cleanup(self):
        super(debuginfo_present, self).cleanup()
        self.sub_stuff['magic'].close()
