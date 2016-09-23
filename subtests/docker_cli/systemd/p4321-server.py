#!/usr/bin/env python

import time
import socket
import SocketServer

PORT = 4321


class requesthandler(SocketServer.BaseRequestHandler):

    def setup(self):
        self.now = time.time()

    def handle(self):
        self.request.sendall(str(int(self.now)) + '\n')

    def finish(self):
        self.request.shutdown(socket.SHUT_RDWR)
        self.request.close()


class forkingtcpserver(SocketServer.ForkingTCPServer):

    address_family = socket.AF_INET
    allow_reuse_address = True
    socket_type = socket.SOCK_STREAM


if __name__ == "__main__":
    server = forkingtcpserver(('0.0.0.0', PORT), requesthandler)
    server.serve_forever()
