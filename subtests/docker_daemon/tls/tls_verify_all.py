"""
Test docker tls verification.

1) Create CA certificate
2) Create certificate for daemon
3) Create certificate for client
4) Verify if docker tls verification works properly.
"""
from dockertest.output import OutputGood
from tls import tls_verify_all_base


class tls_verify_all(tls_verify_all_base):

    def postprocess(self):
        super(tls_verify_all, self).postprocess()

        OutputGood(self.sub_stuff['bash1'])
