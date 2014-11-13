"""
Test sending signal to created but not started container returns successfully
"""

import signal
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.output import OutputGood
from create import create_base


class create_signal(create_base):

    def initialize(self):
        super(create_signal, self).initialize()
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
        sigdkrcmd = mustpass(sigdkrcmd.execute())
        self.sub_stuff['sigdkrcmd'] = sigdkrcmd

    def postprocess(self):
        super(create_signal, self).postprocess()
        sigdkrcmd = self.sub_stuff['sigdkrcmd']
        OutputGood(sigdkrcmd)
        self.failif(sigdkrcmd.exit_status != 0,
                    "Signaling created container returnd non-zero")
        # On success, docker kill should echo back CID of container
        expected_cid = self.get_cid()
        returned_cid = self.get_cid(sigdkrcmd)
        self.failif(expected_cid != returned_cid,
                    "Container CID does not match kill --signal output")
