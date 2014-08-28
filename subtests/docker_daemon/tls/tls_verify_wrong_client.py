"""
Test docker tls. Try to connect to server with wrong client certificates.
Client should return exitstatus different from 0 and should contain
"bad certificate" in stderr.
daemon --tlsverify,--tlscacert=ca.crt,--tlscert=server.crt,--tlskey=server.key
client --tlsverify,--tlscacert=ca.crt,--tlscert=wrongclient.crt,\
    --tlskey=wrongclient.key

1) restart daemon with tls configuration
2) Try to start docker client with wrong certs.
3) Check if client fail.
4) cleanup all containers and images.
"""

from dockertest.output import OutputGood
from tls import tls_verify_all_base_bad


class tls_verify_wrong_client(tls_verify_all_base_bad):

    def initialize(self):
        super(tls_verify_wrong_client, self).initialize()
        self.sub_stuff["check_container_name"] = False

    def postprocess(self):
        super(tls_verify_wrong_client, self).postprocess()

        OutputGood(self.sub_stuff['bash1'], skip=["error_check"])

        self.failif(self.sub_stuff['bash1'].exit_status == 0,
                    "The connection from client with wrong certificate to"
                    " docker daemon should fail.")

        self.failif("bad certificate" not in self.sub_stuff['bash1'].stderr,
                    "Docker should detect if certificate if bad.")
