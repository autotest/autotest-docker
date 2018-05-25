"""
Test sending signal to created but not started container exits non-zero.
"""

import signal
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustfail
from dockertest.output import OutputNotBad
from dockertest.output import DockerVersion
from create import create_base


class create_signal(create_base):

    #: The exit behavior changed in docker version and later
    non_zero_exit_version = "1.8.2"

    def initialize(self):
        super(create_signal, self).initialize()
        DockerVersion().require_client(self.non_zero_exit_version)
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
        expect_status = 1
        if DockerVersion().is_podman:
            expect_status = 125
        sigdkrcmd_result = mustfail(sigdkrcmd.execute(), expect_status)
        self.sub_stuff['sigdkrcmd'] = sigdkrcmd_result

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
