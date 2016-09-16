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
from autotest.client import utils
from dockertest import subtest
from dockertest.subtest import SubSubtest


class packaging(subtest.SubSubtestCaller):

    """ SubSubtest caller """

    def initialize(self):
        self.failif_not_redhat()
        super(packaging, self).initialize()


class packaging_base(SubSubtest):
    pass


class debuginfo_present(packaging_base):
    """
    bz1280068 - make sure docker binary is shipped with debug info.
    """

    @staticmethod
    def _filetype(path):
        return utils.run("file %s" % path).stdout.strip()

    def run_once(self):
        super(debuginfo_present, self).run_once()
        # Another way to search for DWARF might be:
        #    readelf -S /usr/bin/docker-current |grep -i debug_info
        for binfile in ['docker-current', 'docker-latest']:
            path = os.path.join('/usr/bin', binfile)
            if os.path.exists(path):
                self.failif_not_in('not stripped', self._filetype(path),
                                   '%s binary is stripped of debuginfo' % path)
