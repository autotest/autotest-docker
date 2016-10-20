r"""
Summary
---------

Verify that docker, daemons, and containers all have expected
selinux labels.

Operational Summary
----------------------

#. Execute bundled test.sh script to perform label checking operations.
#. Fail subtest if script returns non-zero.

Prerequisites
---------------

Commands contained w/in test script are available/functional on system.
Specifically docker 1.12 is needed for dockerd and containerd.
"""

from os.path import join
from autotest.client.utils import run
from dockertest import subtest
from dockertest.images import DockerImages
from dockertest.output.validate import mustpass
from dockertest.output.dockerversion import DockerVersion


class selinux_labels(subtest.Subtest):

    def initialize(self):
        # See Prerequisites (above)
        DockerVersion().require_server("1.12")
        self.stuff['result'] = None
        self.stuff['di'] = DockerImages(self)
        super(selinux_labels, self).initialize()

    def run_once(self):
        super(selinux_labels, self).run_once()
        # Assumes script exits non-zero on test-failure and
        # cleans up any/all containers/images it created
        result = run("%s %s"
                     % (join(self.bindir, 'test.sh'),
                        self.stuff['di'].default_image),
                     ignore_status=True)
        self.stuff['result'] = result

    def postprocess(self):
        super(selinux_labels, self).postprocess()
        mustpass(self.stuff['result'])
