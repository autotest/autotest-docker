"""
Test sending signal to created but not started container exits non-zero.
"""

import signal
# There is a bug in Pylint + virtualenv that makes this fail in Travis CI
# https://github.com/PyCQA/pylint/issues/73
from distutils.version import LooseVersion  # pylint: disable=E0611
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustfail
from dockertest.output import mustpass
from dockertest.output import OutputNotBad
from dockertest.output import DockerVersion
from dockertest.xceptions import DockerTestNAError
from create import create_base


class create_signal(create_base):

    #: The exit behavior changed in docker version and later
    non_zero_exit_version = "1.8.2"

    def is_newer_docker(self):
        ver_stdout = mustpass(DockerCmd(self, "version").execute()).stdout
        dv = DockerVersion(ver_stdout)
        client_version = LooseVersion(dv.client)
        dep_version = LooseVersion(self.non_zero_exit_version)
        if client_version < dep_version:
            return False
        else:
            return True

    def initialize(self):
        super(create_signal, self).initialize()
        if not self.is_newer_docker():
            raise DockerTestNAError("Test does not support "
                                    "docker version < %s",
                                    self.non_zero_exit_version)
        self.sub_stuff['sigdkrcmd'] = None

    def run_once(self):
        super(create_signal, self).run_once()
        cont = self.sub_stuff['cont']
        sig = getattr(signal, self.config['listen_signal'])
        cont.kill_signal = sig
        # Should not fail
        sigdkrcmd = DockerCmd(self, 'kill',
                              ['--signal', str(sig),
                               self.get_cid()])
        sigdkrcmd = mustfail(sigdkrcmd.execute())
        self.sub_stuff['sigdkrcmd'] = sigdkrcmd

    def postprocess(self):
        super(create_signal, self).postprocess()
        sigdkrcmd = self.sub_stuff['sigdkrcmd']
        OutputNotBad(sigdkrcmd)
        self.failif(sigdkrcmd.exit_status == 0,
                    "Signaling created container exited zero")
        # On failure, docker kill should NOT echo back CID of container
        expected_cid = ''
        returned_cid = expected_cid
        try:
            expected_cid = self.get_cid()
            returned_cid = self.get_cid(sigdkrcmd)
        except IndexError:
            pass
        self.failif(expected_cid == returned_cid,
                    "Container CID returned from failed kill: %s"
                    % sigdkrcmd.stdout)
