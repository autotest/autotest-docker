"""
Test docker tls connection test check only server identity using ca.crt
daemon -d,--selinux-enabled,--tls,--tlscert=server.crt,--tlskey=server.key
client %(docker_options)s,--tlsverify,--tlscacert=ca.crt

1) restart daemon with tls configuration
2) Check client connection
3) cleanup all containers and images.
"""
from dockertest.output import OutputGood
from tls import tls_verify_all_base


class tls_verify_only_server(tls_verify_all_base):

    def postprocess(self):
        super(tls_verify_only_server, self).postprocess()

        OutputGood(self.sub_stuff['bash1'])
