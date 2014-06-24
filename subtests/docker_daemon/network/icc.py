"""
Test docker network driver. Test if inter-container communication work properly.

1) restart daemon with icc=false (forbid communication)
   in network_base.initialize
2) start container1 and get their ip addr
3a) Try to connect containers with python
       Start script for listening
            python -c 'import socket; s = socket.socket();
                       s.bind(("0.0.0.0", 8081)); w = s.listen(10);
                       w,_ = s.accept(); w.sendall("works");
                       w.close(); s.close()'
       start container2 and try to connect and recv from container1
            python -c 'import socket; s = socket.socket();
                       s.connect(("192.168.100.1", 8081)); print s.recv(100);
                       s.close();
3b) If python is not found fall back to ping
4) fail if communication pass from container2 to container1
"""

import os
import time
from dockertest.output import OutputGood, wait_for_output
from dockertest.images import DockerImage
from dockertest.config import get_as_list
from dockertest.xceptions import DockerTestNAError
from network import network_base, AsyncDockerCmdSpec


class icc(network_base):

    def initialize(self):
        super(icc, self).initialize()

        fin = DockerImage.full_name_from_defaults(self.config)

        self.sub_stuff["cont1_name"] = self.conts.get_unique_name("server")
        self.sub_stuff["containers"].append(self.sub_stuff["cont1_name"])
        args1 = get_as_list(self.config["docker_cmd1_args"])
        args1.append("--name=%s" % (self.sub_stuff["cont1_name"]))
        args1.append(fin)
        self.sub_stuff["bash1"] = self.dkr_cmd.async("run", args1 + ["sh"],
                                               stdin_r=AsyncDockerCmdSpec.PIPE)

        self.sub_stuff["cont2_name"] = self.conts.get_unique_name("client")
        self.sub_stuff["containers"].append(self.sub_stuff["cont2_name"])
        args2 = get_as_list(self.config["docker_cmd2_args"])
        args2.append("--name=%s" % (self.sub_stuff["cont2_name"]))
        args2.append(fin)
        self.sub_stuff["bash2"] = self.dkr_cmd.async("run", args2 + ["sh"],
                                               stdin_r=AsyncDockerCmdSpec.PIPE)

        ip = self.get_container_ip(self.sub_stuff["cont1_name"])
        if ip is None:
            raise DockerTestNAError("Problems during initialization of"
                                    " test: Cannot get container IP addr.")
        self.sub_stuff["ip1"] = ip

    def run_cmd(self, bash_stdin, cmd):
        self.logdebug("send command to container:\n%s" % (cmd))
        os.write(bash_stdin, cmd)


    def run_once(self):
        super(icc, self).run_once()
        # 1. Run with no options
        # Try to connect containers using python.
        self.run_cmd(self.sub_stuff["bash1"].stdin,
                     "python -c 'import socket; s = socket.socket();"
                     " s.bind((\"0.0.0.0\", 8081)); w = s.listen(10);"
                     " w,_ = s.accept(); w.sendall(\"PING 64 bytes\");"
                     " w.close(); s.close()'\n")
        time.sleep(1)
        self.run_cmd(self.sub_stuff["bash2"].stdin,
                     "python -c 'print \"PING\"; import socket;"
                     "s = socket.socket(); s.connect((\"%s\", 8081));"
                     " print \"Recv:\" + s.recv(100); s.close();'\n" %
                     self.sub_stuff["ip1"])

        #Wait for possible ping passing.
        out_fn = lambda: self.sub_stuff["bash2"].stdout
        wait_for_output(out_fn, "64 bytes", 10)
        if "python: not found" in out_fn():
            self.logdebug("Fall back to command ping")
            self.run_cmd(self.sub_stuff["bash2"].stdin,
                         "ping %s\n" % self.sub_stuff["ip1"])
            wait_for_output(out_fn, "64 bytes", 10)

        self.sub_stuff["bash1"].wait(1)
        self.sub_stuff["bash2"].wait(1)

    def postprocess(self):
        super(icc, self).postprocess()

        OutputGood(self.sub_stuff['bash1'])
        OutputGood(self.sub_stuff['bash2'], ignore_error=True)
        stdout = self.sub_stuff["bash2"].stdout
        self.logdebug("Stdout: %s" % (stdout))
        self.failif("PING" not in stdout,
                    "Something wrong happens during test: %s" % stdout)
        self.failif("64 bytes" in stdout,
                    "Destination should be unrecheable because docker should"
                    " separate containers's when parameter --icc=false in"
                    " daemon configuration. Detatil: %s" % stdout)

    def cleanup(self):
        # Kill docker_daemon process
        super(icc, self).cleanup()

        if "bash1" in self.sub_stuff:
            self.sub_stuff["bash1"].close()
        if "bash2" in self.sub_stuff:
            self.sub_stuff["bash2"].close()
