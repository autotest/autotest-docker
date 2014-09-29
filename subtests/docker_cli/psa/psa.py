r"""
Summary
----------

Verify the table output and formatting of the ``docker ps -a``
command.

Operational Summary
----------------------

#. Attempt to parse 'docker ps -a --no-trunc --size' table output
#. Fail if table-format changes or is not parseable
"""

import time
import signal
import os.path
import os
from autotest.client import utils
from dockertest import subtest
from dockertest import images
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.containers import DockerContainers
from dockertest.xceptions import DockerTestFail


class psa(subtest.Subtest):
    config_section = 'docker_cli/psa'

    def initialize(self):
        super(psa, self).initialize()
        dc = self.stuff['dc'] = DockerContainers(self)
        dc.verify_output = True  # test subject, do extra checking
        name = self.stuff['container_name'] = dc.get_unique_name()
        cidfile = os.path.join(self.tmpdir, 'cidfile')
        self.stuff['cidfile'] = cidfile
        subargs = ['--cidfile', cidfile,
                   '--name=%s' % name]
        fin = images.DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append('/bin/bash')
        subargs.append('-c')
        # Write to a file when signal received
        # Loop forever until marker-file exists
        command = ("\""
                   "echo 'foobar' > stop && "
                   "rm -f stop && trap '/usr/bin/date +%%s> stop' USR1 && "
                   "while ! [ -f stop ]; do /usr/bin/sleep 0.1s; done"
                   "\"")
        subargs.append(command)
        self.stuff['cl0'] = dc.list_containers()
        dkrcmd = AsyncDockerCmd(self, 'run', subargs)
        self.stuff['dkrcmd'] = dkrcmd
        if os.path.isfile(cidfile):
            os.unlink(cidfile)

    def cidfile_has_cid(self):
        """
        Docker ps output updated once container assigned a CID
        """
        cidfile = self.stuff['cidfile']
        if os.path.isfile(cidfile):
            cid = open(cidfile, 'rb').read().strip()
            if len(cid) >= 12:
                self.stuff['container_id'] = cid
                return True
        return False

    def wait_start(self):
        self.stuff['dkrcmd'].execute()
        self.failif(not utils.wait_for(func=self.cidfile_has_cid,
                                       timeout=self.config['docker_timeout'],
                                       text="Waiting for container to start"))

    def run_once(self):
        super(psa, self).run_once()
        self.wait_start()
        self.loginfo("Container running, waiting %d seconds to examine"
                     % self.config['wait_start'])
        time.sleep(self.config['wait_start'])
        self.logdebug("Post-wait status: %s", self.stuff['dkrcmd'])
        dc = self.stuff['dc']
        self.stuff['cl1'] = dc.list_containers()
        sig = getattr(signal, 'SIGUSR1')
        self.loginfo("Signaling container with signal %s", sig)
        json = dc.json_by_name(self.stuff['container_name'])
        self.failif(not json[0]["State"]["Running"],
                    "Can't signal non-running container, see debug "
                    "log for more detail")
        pid = int(json[0]["State"]["Pid"])
        self.failif(not utils.signal_pid(pid, sig),
                    "Failed to cause container exit with signal: "
                    "still running, see debug log for more detail.")
        self.loginfo("Waiting up to %d seconds for exit",
                     self.config['wait_stop'])
        self.stuff['cmdresult'] = self.stuff['dkrcmd'].wait(
            self.config['wait_stop'])
        self.stuff['cl2'] = dc.list_containers()

    def postprocess(self):
        super(psa, self).postprocess()
        OutputGood(self.stuff['cmdresult'], "test container failed on start")
        dc = self.stuff['dc']
        cnts = dc.list_containers_with_name(self.stuff['container_name'])
        self.failif(len(cnts) < 1, "Test container not found in list")
        cnt = cnts[0]
        estat1 = str(cnt.status).startswith("Exit 0")  # pre docker 0.9.1
        estat2 = str(cnt.status).startswith("Exited (0)")  # docker 0.9.1+
        msg = ("Exit status mismatch: %s does not"
               "start with %s or %s"
               % (str(cnt), "Exit 0",
                  "Exited (0)"))
        self.failif(not (estat1 or estat2), msg)
        cid = self.stuff['container_id']
        cl0_ids = [cnt.long_id for cnt in self.stuff['cl0']]
        cl1_ids = [cnt.long_id for cnt in self.stuff['cl1']]
        cl2_ids = [cnt.long_id for cnt in self.stuff['cl2']]
        try:
            self.failif(cid in cl0_ids, "Test container's ID found in ps "
                                        "output before this test started it!")
            self.failif(cid not in cl1_ids, "Test container's ID not found in "
                                            "ps output after starting it")
            self.failif(cid not in cl2_ids, "Test container's ID not found in "
                                            "ps output after it exited")
        except DockerTestFail:
            self.logdebug("Parsed docker ps table before starting: %s",
                          self.stuff['cl0'])
            self.logdebug("Parsed docker ps table after starting: %s",
                          self.stuff['cl1'])
            self.logdebug("Parsed docker ps table after exiting: %s",
                          self.stuff['cl2'])
            raise

    def cleanup(self):
        super(psa, self).cleanup()
        cid = self.stuff.get('container_id')
        if self.config['remove_after_test'] and cid is not None:
            self.logdebug("Cleaning container %s", cid)
            # We need to know about this breaking anyway, let it raise!
            nfdc = DockerCmd(self, "rm", ['--force', '--volumes', cid])
            mustpass(nfdc.execute())
