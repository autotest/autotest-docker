r"""
Summary
----------

Test docker exec by executing basic commands inside already running container
and checking the results.

Operational Summary
----------------------

#.  Execute a shell in a container and leave it idling
#.  In parallel, run a command in container with ``docker exec``
#.  Verify expected result from above step
#.  Cleanup shell container

Prerequisites
---------------

*  Test container contains ``/bin/true`` and ``/bin/false``
*  Test container contains ``find`` command
*  Test container's ``/proc`` filesystem is accessable by ``docker exec``
"""


import os
import time
from dockertest.subtest import SubSubtest, SubSubtestCaller
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.xceptions import DockerTestFail
from dockertest.output import mustpass
from dockertest.output import mustfail
from dockertest.output import OutputGood
from dockertest.output import OutputNotBad
from dockertest.output import wait_for_output
from dockertest.config import get_as_list


class run_exec(SubSubtestCaller):
    pass


class exec_base(SubSubtest):

    def init_subargs(self):
        run_args = self.sub_stuff['run_args']
        run_options_csv = self.config["run_options_csv"]
        if run_options_csv:
            run_args += get_as_list(run_options_csv)

        run_args.append('--name')
        name = self.sub_stuff['cont'].get_unique_name()
        self.sub_stuff['run_name'] = name
        run_args.append(name)
        fqin = DockerImage.full_name_from_defaults(self.config)
        run_args.append(fqin)
        bash_cmd = self.config['bash_cmd']
        if bash_cmd:
            run_args += get_as_list(bash_cmd)

        exec_args = self.sub_stuff['exec_args']
        exec_options_csv = self.config["exec_options_csv"]
        if exec_options_csv:
            exec_args += get_as_list(exec_options_csv)
        exec_args.append(name)

    def start_base_container(self):
        reader, writer = os.pipe()
        # Exception could occur before os.close(reader) below
        self.sub_stuff['fds'].append(reader)
        self.sub_stuff['fds'].append(writer)
        self.sub_stuff['dkrcmd_stdin'] = writer
        dkrcmd = AsyncDockerCmd(self, 'run', self.sub_stuff['run_args'])
        dkrcmd.execute(reader)
        self.sub_stuff['containers'].append(self.sub_stuff['run_name'])
        os.close(reader)  # not needed anymore
        self.sub_stuff['dkrcmd'] = dkrcmd
        os.write(writer, 'echo "Started"\n')
        if not wait_for_output(lambda: dkrcmd.stdout, "Started"):
            raise DockerTestFail("Unable to start base container:\n %s" %
                                 (dkrcmd))

    def initialize(self):
        super(exec_base, self).initialize()
        self.sub_stuff['containers'] = []
        self.sub_stuff['images'] = []
        self.sub_stuff['cont'] = DockerContainers(self)
        self.sub_stuff['img'] = DockerImages(self)
        self.sub_stuff['fds'] = []  # every fd in here guarantee closed
        self.sub_stuff['dkrcmd_stdin'] = None  # stdin fd for vvvvvvv
        self.sub_stuff['run_name'] = None  # container name for vvvvvvv
        self.sub_stuff['run_args'] = []  # parameters for vvvvvv
        self.sub_stuff['dkrcmd'] = None  # docker run ... container
        self.sub_stuff['exec_args'] = []  # parameters for vvvvvv
        self.sub_stuff['dkrcmd_exec'] = None  # docker exec ... container
        self.init_subargs()
        self.start_base_container()

    def postprocess(self):
        super(exec_base, self).postprocess()  # Prints out basic info
        os.write(self.sub_stuff['dkrcmd_stdin'], 'exit\t')
        time.sleep(1)
        mustpass(DockerCmd(self, 'kill',
                           [self.sub_stuff['run_name']]).execute())
        # It may have been killed, but exec is what we care about
        OutputNotBad(self.sub_stuff['dkrcmd'].cmdresult)

    def cleanup(self):
        super(exec_base, self).cleanup()
        for ifd in self.sub_stuff['fds']:
            try:
                os.close(ifd)
            except OSError:
                pass
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            dc.clean_all(self.sub_stuff.get("containers"))
            di = DockerImages(self)
            di.clean_all(self.sub_stuff.get("images"))


class exec_true(exec_base):

    def run_once(self):
        super(exec_true, self).run_once()
        subargs = self.sub_stuff['exec_args'] + ['/bin/true']
        dkrcmd_exec = DockerCmd(self, 'exec', subargs, timeout=60)
        self.sub_stuff['dkrcmd_exec'] = dkrcmd_exec
        dkrcmd_exec.execute()

    def postprocess(self):
        dkrcmd_exec = self.sub_stuff['dkrcmd_exec']
        mustpass(dkrcmd_exec.cmdresult)
        OutputGood(dkrcmd_exec.cmdresult)
        super(exec_true, self).postprocess()


class exec_false(exec_base):

    def run_once(self):
        super(exec_false, self).run_once()
        subargs = self.sub_stuff['exec_args'] + ['/bin/false']
        dkrcmd_exec = DockerCmd(self, 'exec', subargs, timeout=60)
        self.sub_stuff['dkrcmd_exec'] = dkrcmd_exec
        dkrcmd_exec.execute()

    def postprocess(self):
        dkrcmd_exec = self.sub_stuff['dkrcmd_exec']
        mustfail(dkrcmd_exec.cmdresult)
        OutputNotBad(dkrcmd_exec.cmdresult)
        super(exec_false, self).postprocess()


class exec_pid_count(exec_base):

    def run_once(self):
        super(exec_pid_count, self).run_once()
        subargs = self.sub_stuff['exec_args']
        subargs.append("find /proc -maxdepth 1 -a -type d -a "
                       "-regextype posix-extended -a "
                       r"-regex '/proc/[0-9]+'")
        dkrcmd_exec = DockerCmd(self, 'exec', subargs)
        self.sub_stuff['dkrcmd_exec'] = dkrcmd_exec
        dkrcmd_exec.execute()

    def postprocess(self):
        dkrcmd_exec = self.sub_stuff['dkrcmd_exec']
        mustpass(dkrcmd_exec.cmdresult)
        OutputGood(dkrcmd_exec.cmdresult)
        pids = dkrcmd_exec.stdout.strip().splitlines()
        expected = self.config["pid_count"]
        self.failif(len(pids) != expected,
                    "Expecting %d pids: %s"
                    % (expected, pids))
        super(exec_pid_count, self).postprocess()
