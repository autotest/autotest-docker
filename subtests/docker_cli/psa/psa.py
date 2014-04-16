"""
Test output of docker ps -a command

1. Attempt to parse 'docker ps -a --no-trunc --size' table output
2. Fail if table-format changes or is not parseable
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import time, signal, os.path
from autotest.client import utils
from dockertest import subtest
from dockertest import images
from dockertest.output import OutputGood
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.containers import DockerContainers

class psa(subtest.Subtest):
    config_section = 'docker_cli/psa'

    def initialize(self):
        super(psa, self).initialize()
        name = self.stuff['container_name'] = utils.generate_random_string(8)
        cidfile = os.path.join(self.tmpdir, 'cidfile')
        subargs = ['--cidfile', cidfile, '--detach',
                   '--sig-proxy', '--name=%s' % name]
        fin = images.DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append('/bin/bash')
        subargs.append('-c')
        # Write to a file when signal received
        # Loop forever until marker-file exists
        command = ("\"rm -f stop; trap '/usr/bin/date > stop' SIGURG; "
                   "while ! [ -f stop ]; do :; done\"")
        subargs.append(command)
        self.stuff['cl0'] = DockerContainers(self, 'cli').get_container_list()
        dkrcmd = DockerCmd(self, 'run', subargs)
        self.stuff['cmdresult'] = dkrcmd.execute()
        self.stuff['container_id'] = open(cidfile, 'rb').read().strip()

    def run_once(self):
        super(psa, self).run_once()
        OutputGood(self.stuff['cmdresult'], "test container failed on start")
        self.loginfo("Container running, waiting %d seconds to examine"
                     % self.config['wait_start'])
        time.sleep(self.config['wait_start'])
        # This is the test-subject, need to check output of docker command
        clic = DockerContainers(self, 'clic')
        self.stuff['cl1'] = clic.get_container_list()
        sig = getattr(signal, 'SIGURG')  # odd-ball, infreq. used.
        self.loginfo("Signaling container with signal %s", sig)
        nfdc = NoFailDockerCmd(self, 'kill', ['--signal', "URG",
                                              self.stuff['container_id']])
        nfdc.execute()
        self.loginfo("Waiting up to %d seconds for exit",
                     self.config['wait_stop'])
        time.sleep(self.config['wait_stop'])
        # Final listing, expect container to have exited
        self.stuff['cl2'] = clic.get_container_list()

    def postprocess(self):
        super(psa, self).postprocess()
        cl0_len = len(self.stuff['cl0'])
        cl1_len = len(self.stuff['cl1'])
        cl2_len = len(self.stuff['cl2'])
        self.failif(cl1_len <= cl0_len, "Container list length did not "
                                        "increase.")
        self.failif(cl1_len != cl2_len, "Third container list length did "
                                        "not stay same as second list.")
        # TODO: Use 'inspect' command output to get actual PID
        #       and utils.pid_is_alive(PID) to verify it's stopped
        # Might as well do some more checking
        dc = DockerContainers(self, 'cli')  # check output
        cnts = dc.list_containers_with_name(self.stuff['container_name'])
        self.failif(len(cnts) < 1, "Test container not found in list")
        cnt = cnts[0]
        status = str(cnt.status)
        expected1 = 'Exit 0'
        expected2 = 'Exited (0)'
        status_good = (bool(status.count(expected1)) or
                       bool(status.count(expected2)))
        self.failif(not status_good, "Exit status mismatch: %s" % status)

    def cleanup(self):
        super(psa, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if ( (self.config['remove_after_test']) and
             (self.stuff.get('container_id') is not None) ):
            long_id = self.stuff['container_id']
            # We need to know about this breaking anyway, let it raise!
            nfdc = NoFailDockerCmd(self, "rm", ['--force',
                                                '--volumes', long_id])
            nfdc.execute()
