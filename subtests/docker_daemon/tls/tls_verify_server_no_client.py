"""
Test docker tls connection test check only server identity using ca.crt server
do not check wrong certificate from passed from client.
daemon --tls,--tlscert=server.crt,--tlskey=server.key
client --tlsverify,--tlscacert=ca.crt,--tlscert=wrongclient.crt,--tlskey=wrongclient.key

1) restart daemon with tls configuration
2) Check client connection
3) cleanup all containers and images.
"""
from dockertest.output import OutputGood
from tls import tls_verify_all_base_bad


class tls_verify_server_no_client(tls_verify_all_base_bad):

    def postprocess(self):
        super(tls_verify_server_no_client, self).postprocess()

        OutputGood(self.sub_stuff['bash1'])
