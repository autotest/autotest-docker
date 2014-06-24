"""
Test containers can send log to host

1. Mount the /dev/log/ directory to container.
2. Use `logger` send a message.
3. Verify that could see the message on host.
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import os
import datetime
from dockertest.subtest import Subtest
from dockertest.dockercmd import NoFailDockerCmd, DockerCmd
from dockertest.images import DockerImage
from dockertest.containers import DockerContainers


class syslog(Subtest):
    def initialize(self):
        super(syslog, self).initialize()
        dc = DockerContainers(self)
        scn = self.__class__.__name__
        name = self.stuff["container_name"] = dc.get_unique_name(prefix=scn)
        self.stuff['name'] = '--name=%s' % name
        self.stuff['fin'] = DockerImage.full_name_from_defaults(self.config)
        self.stuff['params'] = '-v /dev/log:/dev/log'
        now = datetime.datetime.now()
        time = now.strftime("%Y-%m-%d %H:%M:%S")
        self.stuff["msg"] = "SYSLOGTEST at time: %s" % time
        self.stuff['testcmds'] = 'logger %s' % self.stuff["msg"]

    def run_once(self):
        super(syslog, self).run_once()
        subargs = [self.stuff['name'],
                   self.stuff['params'],
                   self.stuff['fin'],
                   self.stuff['testcmds']]

        nfdc = NoFailDockerCmd(self, "run", subargs)
        self.stuff['cmdresults'] = nfdc.execute()

    def postprocess(self):
        super(syslog, self).postprocess()
        _command = self.stuff['cmdresults'].command
        self.loginfo("Commands: %s" % _command)
        _status = self.stuff['cmdresults'].exit_status
        self.failif(_status, str(self.stuff['cmdresults'].stderr))
        _check = self.verify_message_logged()
        self.failif(not _check, "syslog test failed")

    def verify_message_logged(self):
        with open("/var/log/messages") as f:
            f.seek(-4096, os.SEEK_END)
            for line in f:
                if line.strip().endswith(self.stuff["msg"]):
                    self.loginfo(line.strip())
                    return True

    def cleanup(self):
        super(syslog, self).cleanup()
        if self.config['remove_after_test']:
            dkrcmd = DockerCmd(self, 'rm', [self.stuff['container_name']])
            dkrcmd.execute()
