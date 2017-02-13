r"""
Summary
---------

Test monitoring containers logs from host via bind-mount
/dev/log to containers.  Test containers can send log to host

Operational Summary
----------------------

#. Mount the /dev/log/ directory to container.
#. Use `logger` send a message.
#. Verify that could see the message on host.

Prerequisites
----------------
*  Docker daemon is running and accessible by it's unix socket.
*  /dev/log is existing and could be mounted to containers.
"""

import os
import os.path
import datetime
from dockertest.subtest import Subtest
from dockertest.output import mustpass
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.containers import DockerContainers
from dockertest.xceptions import DockerTestNAError, DockerTestFail


class syslog(Subtest):

    def initialize(self):
        super(syslog, self).initialize()
        if not os.path.isfile(self.config['syslogfile']):
            raise DockerTestNAError("Couldn't find system log: %s"
                                    % self.config['syslogfile'])
        dc = DockerContainers(self)
        name = self.stuff["container_name"] = dc.get_unique_name()
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

        # New syslog output must be after the current syslog file end
        self.stuff['syslog_fh'] = open(self.config['syslogfile'])
        self.stuff['syslog_fh'].seek(0, os.SEEK_END)

        nfdc = DockerCmd(self, "run", subargs)
        self.stuff['cmdresults'] = mustpass(nfdc.execute())

    def postprocess(self):
        super(syslog, self).postprocess()
        _command = self.stuff['cmdresults'].command
        self.loginfo("Commands: %s" % _command)
        _status = self.stuff['cmdresults'].exit_status
        self.failif(_status, str(self.stuff['cmdresults'].stderr))
        self.verify_message_logged()

    def verify_message_logged(self):
        for line in self.stuff['syslog_fh']:
            if line.strip().endswith(self.stuff["msg"]):
                self.loginfo("Found in syslog: %s" % line.strip())
                self.stuff['syslog_fh'].close()
                return
        raise DockerTestFail("Did not find expected message '%s'"
                             " in syslog file %s" %
                             (self.stuff["msg"], self.config['syslogfile']))

    def cleanup(self):
        super(syslog, self).cleanup()
        if self.config['remove_after_test']:
            dkrcmd = DockerCmd(self, 'rm', [self.stuff['container_name']])
            dkrcmd.execute()
