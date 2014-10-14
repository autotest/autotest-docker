r"""
Summary
---------

Test usage of docker 'top' command

Operational Summary
----------------------

#. start container with bash
#. execute docker top and container ps
#. in container execute couple of processes
#. execute docker top and container ps
#. stop container
#. execute docker top
#. analyze results

Prerequisites
---------------------------------------------

*  A docker image capable of executing the ``top`` command
"""

import os
import re
import time

from dockertest import config, subtest, xceptions
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.dockercmd import MustFailDockerCmd
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.xceptions import DockerTestNAError


class top(subtest.Subtest):

    """ Subtest caller """
    config_section = 'docker_cli/top'
    # F,UID,(PID),(PPID),(PRI),(NI),(VSZ),(RSS),(WCHAN),(STAT),(TTY),TIME,CMD
    __re_top_all = re.compile(r'\d+\s+\d+\s+(?P<pid>\d+)\s+(?P<ppid>\d+)\s+'
                              r'(?P<pri>\d+)\s+(?P<ni>\d+)\s+(?P<vsz>\d+)\s+'
                              r'(?P<rss>\d+)\s+(?P<wchan>\w+|-|\?)\s+'
                              r'(?P<stat>[DRSTWXZ])[<NLsl+]*\s+'
                              r'(?P<tty>[^ ]+)\s+\d+:\d+\s*')

    def _init_stuff(self):
        """ Initialize stuff """
        self.stuff['container_name'] = None     # name of the container
        self.stuff['container_cmd'] = None      # tested container
        self.stuff['docker_top'] = []           # os outputs from host
        self.stuff['container_ps'] = []         # ps output from containers
        self.stuff['stop_cmd'] = None           # cmd to stop test cmds
        # Permissable exceptions to ignore for stop_cmd
        self.stuff['stop_xcpt'] = (OSError, IOError, ValueError)

    def _init_container(self):
        """ Create, store in self.stuff and execute container """
        try:
            fin = DockerImage.full_name_from_defaults(self.config)
        except ValueError:
            raise DockerTestNAError("Empty test image name configured,"
                                    "did you set one for this test?")

        docker_containers = DockerContainers(self)
        name = docker_containers.get_unique_name()
        self.stuff['container_name'] = name
        if self.config.get('run_options_csv'):
            subargs = [arg for arg in
                       self.config['run_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append("--name %s" % name)

        subargs.append(fin)
        subargs.append("bash")
        container = NoFailDockerCmd(self, 'run', subargs)
        self.stuff['container_cmd'] = container
        container.execute()

        if self.config.get('attach_options_csv'):
            subargs = [arg for arg in
                       self.config['attach_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append(name)
        container = AsyncDockerCmd(self, 'attach', subargs)
        self.stuff['container_cmd'] = container  # overwrites finished cmd
        stdin = os.pipe()
        self.stuff['container_stdin'] = stdin[1]
        container.execute(stdin[0])

    def initialize(self):
        super(top, self).initialize()
        self._init_stuff()
        config.none_if_empty(self.config)
        self._init_container()

    def _gather_processes(self, last_idx=0, fail=False):
        """
        Gathers `docker top` and in-container `ps` output and stores it in
        `self.stuff`.
        """
        if not fail:
            cmd = NoFailDockerCmd(self, "top", [self.stuff['container_name'],
                                                'all'])
            out = cmd.execute().stdout.splitlines()
            self.stuff['docker_top'].append(out)
        else:
            cmd = MustFailDockerCmd(self, "top", [self.stuff['container_name'],
                                                  'all'])
            out = cmd.execute()
            self.stuff['docker_top'].append(out)
            return

        cont_cmd = self.stuff['container_cmd']
        os.write(self.stuff['container_stdin'], "ps all\n")

        new_idx = last_idx
        endtime = time.time() + 5
        while time.time() < endtime:
            out = cont_cmd.stdout.splitlines()
            if len(out) <= last_idx:
                continue
            i = last_idx
            for i in xrange(last_idx, len(out)):
                if "ps all" in out[i]:    # wait for the command to appear
                    break
            else:   # "ps all" not in output, wait a bit longer
                continue
            if new_idx == len(out):    # wait twice for the same output
                out = out[i + 1:]   # cut everything before this cmd execution
                # cut the last line (bash prompt)
                if out and not self.__re_top_all.match(out[-1]):
                    out = out[:-1]
                break
            new_idx = len(out)
            time.sleep(0.05)
        else:
            raise xceptions.DockerTestFail("No new output after 'ps' command "
                                           "executed in the container.")
        self.stuff['container_ps'].append(out)
        return new_idx

    def run_once(self):
        # Execute the top command
        super(top, self).run_once()
        last_idx = self._gather_processes()
        cont_stdin = self.stuff['container_stdin']

        self.stuff['stop_cmd'] = lambda: os.write(cont_stdin, "rm -f "
                                                  "/test_cmd_lock ; exit 0\n")
        os.write(cont_stdin, "touch /test_cmd_lock\n")
        # Execute 10 idle processes
        for _ in xrange(10):
            os.write(cont_stdin, "while [ -e /test_cmd_lock ]; do sleep 1; "
                     "done &\n")
        # Execute 10 busy processes
        for _ in xrange(10):
            os.write(cont_stdin, "while [ -e /test_cmd_lock ]; do :; "
                     "done &\n")

        # time.sleep(3)

        last_idx = self._gather_processes(last_idx)

        self.stuff['stop_cmd']()
        OutputGood(self.stuff['container_cmd'].wait(20))
        self.stuff['stop_cmd'] = None

        self._gather_processes(fail=True)

    def _compare_output(self, ps, d_top, exp_length):
        # TODO: Compare values where it makes sense...
        self.failif(len(ps) - len(d_top) != 1, "in container ps output is "
                    "not of 1 line longer (the ps command). Check the output:"
                    "\ncontainer ps:\n%s\ndocker top:\n%s" % (ps, d_top))
        # each bash script generates additional command in loop.
        self.failif((len(d_top) - 1 < exp_length
                     or len(d_top) - 1 > 2 * exp_length),
                    "Number of processes is not "
                    "between expected (%s) and 2xexpected:\n%s"
                    % (exp_length, d_top))
        i = 0
        for i in xrange(1, len(d_top)):   # skip header
            ps_match = self.__re_top_all.match(ps[i])
            self.failif(not ps_match, "output of 'ps all' inside container "
                        "is corrupted, line %s doesn't match prescription.\n%s"
                        % (i, ps))
            top_match = self.__re_top_all.match(d_top[i])
            self.failif(not top_match, "output of 'docker top' is corrupted, "
                        "line %s doesn't match prescription.\n%s" % (i, d_top))
        ps_match = self.__re_top_all.match(ps[-1])   # check the last one
        self.failif(not ps_match, "output of 'ps all' inside container "
                    "is corrupted, line -1 doesn't match prescription.\n%s"
                    % ps)

    def postprocess(self):
        super(top, self).postprocess()
        self._compare_output(self.stuff['container_ps'][0],
                             self.stuff['docker_top'][0], 1)
        self._compare_output(self.stuff['container_ps'][1],
                             self.stuff['docker_top'][1], 22)

        self.failif("is not running" not in str(self.stuff['docker_top'][2]),
                    "docker top failed as expected, but 'is not running' "
                    "message is not in the output: %s"
                    % (self.stuff['docker_top'][2]))

    def cleanup(self):
        super(top, self).cleanup()
        try:
            if self.stuff.get('stop_cmd'):
                self.stuff['stop_cmd']()    # stop stressers
        finally:
            name = self.stuff.get('container_name')
            if name and self.config.get('remove_after_test'):
                DockerCmd(self, 'rm', ['--force', '--volumes',
                                       name]).execute()
