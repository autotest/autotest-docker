r"""
Summary
-------

Preserve /etc/sysconfig/* as a tarball in the top-level sysinfo dir

Operational Summary
-------------------

#. Do the equivalent of 'tar czf $SYSINFO/sysconfig.tar.gz /etc/sysconfig*'

"""

from shutil import make_archive
import os.path
from dockertest.subtest import Subtest


class log_sysconfig(Subtest):

    def run_once(self):
        super(log_sysconfig, self).run_once()
        # .tar.gz will be added automatically
        base_filepath = os.path.join(self.job.sysinfo.sysinfodir, 'sysconfig')
        make_archive(base_filepath, 'gztar', '/etc', 'sysconfig')
