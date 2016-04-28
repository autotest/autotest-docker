r"""
Summary
---------

Test the docker wait operation on containers in various states

Operational Summary
----------------------

#. Prepare wait target container
#. Execute docker wait on container
#. Verify results
"""

import re
from collections import namedtuple
from collections import OrderedDict
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.images import DockerImages
from dockertest.containers import DockerContainers
from dockertest.output import OutputGood
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.config import Config
from dockertest.config import get_as_list


class wait(SubSubtestCaller):
    pass


Target = namedtuple('Target', ['name', 'fqin', 'setup', 'wait', 'sleep'])


class WaitBase(SubSubtest):

    def init_utils(self):
        sss = self.sub_stuff
        sss['dc'] = DockerContainers(self)
        sss['di'] = DockerImages(self)

    def init_substuff(self):
        self.sub_stuff['targets'] = OrderedDict()
        self.sub_stuff['dkrcmd'] = None

    def target_dkrcmd(self, target):
        # Validate setup command
        if target.setup == 'none':
            return None
        elif target.setup == 'run':
            command = 'run'
        elif target.setup == 'create':
            command = 'create'
        else:
            raise ValueError("Unsupported target setup string: "
                             "%s" % target.setup)
        subargs = get_as_list(self.config['target_run'])
        subargs.append('--name')
        subargs.append(target.name)
        subargs.append(target.fqin)
        target_cmd = self.config['target_cmd'].replace('@SLEEP@',
                                                       str(target.sleep))
        subargs += get_as_list(target_cmd)
        timeout = self.config['target_timeout']
        return DockerCmd(self, command, subargs, timeout=timeout)

    def target_wait_dkrcmd(self, name, fqin, setup, wait_opr, sleep):
        del sleep  # not used for now
        del setup  # not used for now
        del fqin   # not used for now
        if wait_opr == 'stop':
            cmd = 'stop'
            subargs = [name]
        elif wait_opr == 'kill':
            cmd = 'kill'
            subargs = [name]
        elif wait_opr == 'remv':
            cmd = 'rm'
            subargs = ['--force', '--volumes', name]
        elif wait_opr == 'none':
            return None
        elif wait_opr.isdigit():
            cmd = 'kill'
            subargs = ['--signal', wait_opr, name]
        else:
            raise ValueError("Unsupported target_wait %s for target %s"
                             % (wait_opr, name))
        return AsyncDockerCmd(self, cmd, subargs,
                              self.config['target_verbose'])

    def init_targets(self):
        sss = self.sub_stuff
        target_setups = get_as_list(self.config['target_setups'])
        # Single values will auto-convert to int's, convert back to string
        target_waits = get_as_list(str(self.config['target_waits']))
        target_sleeps = get_as_list(str(self.config['target_sleeps']))
        fqin = sss['di'].full_name_from_defaults()
        for index, setup in enumerate(target_setups):
            name = sss['dc'].get_unique_name(setup)
            sleep = float(target_sleeps[index])
            wait_opr = target_waits[index].lower()
            wait_dkr = self.target_wait_dkrcmd(name, fqin,
                                               setup, wait_opr.lower(), sleep)
            target = Target(name=name, fqin=fqin,
                            setup=setup.lower(),
                            wait=wait_dkr, sleep=sleep)
            sss['targets'][target] = self.target_dkrcmd(target)

    def execute_targets(self):
        for dkrcmd in self.sub_stuff['targets'].itervalues():
            dkrcmd.execute()  # blocking + detached

    def execute_target_waits(self):
        for target in self.sub_stuff['targets']:
            if target.wait is not None:
                self.logdebug("Target %s", target.name)
                target.wait.execute()  # async

    def finish_target_waits(self):
        for target in self.sub_stuff['targets']:
            if target.wait is not None:
                target.wait.wait(self.config['target_timeout'])
            if self.config['target_verbose']:
                self.logdebug("Final target %s details: %s",
                              target.name, target.wait)

    def initialize(self):
        super(WaitBase, self).initialize()
        self.init_utils()
        self.init_substuff()
        self.init_targets()

    def run_once(self):
        super(WaitBase, self).run_once()
        sss = self.sub_stuff
        subargs = [target.name for target in sss['targets']]
        # timeout set automatically from docker_timeout
        sss['dkrcmd'] = AsyncDockerCmd(self, 'wait', subargs,
                                       verbose=self.config['wait_verbose'])
        self.execute_targets()
        sss['dkrcmd'].execute()
        self.execute_target_waits()
        sss['dkrcmd'].wait(self.config['docker_timeout'])
        self.finish_target_waits()

    def pproc_outputgood(self):
        self.logdebug("Checking output sanity")
        OutputGood(self.sub_stuff['dkrcmd'].cmdresult)

    def pproc_exit(self):
        self.logdebug("Checking wait exit code")
        _exit = self.config['exit']
        if not str(_exit).isdigit():
            return
        dkrcmd_exit = self.sub_stuff['dkrcmd'].exit_status
        expect_exit = int(_exit)
        self.failif_ne(dkrcmd_exit, expect_exit, "Wait exit")

    def pproc_stdio(self, which):
        stdio = self.config[which]
        if not isinstance(stdio, basestring) or stdio == '':
            self.logdebug("Not checking %s", which)
            return
        self.logdebug("Checking %s", which)
        regex = re.compile(stdio)
        dkrcmd_stdio = getattr(self.sub_stuff['dkrcmd'], which)
        self.failif(not regex.search(dkrcmd_stdio),
                    "Wait %s didn't match regex %s in %s"
                    % (which, stdio, dkrcmd_stdio))

    def pproc_target(self, target, dkrcmd):
        self.logdebug("Checking target %s", target.name)
        exit_status = dkrcmd.exit_status
        if exit_status != 0:
            msg = ("Target container %s non-zero exit(%d), "
                   "see debuglog for details"
                   % (target.name, exit_status))
            self.logwarning(msg)
            self.logdebug(str(dkrcmd))

    def pproc_target_waits(self, target):
        if target.wait is None:
            return  # Nothing to check
        self.logdebug("Checking target %s wait command", target.name)
        if self.config['target_verbose']:
            self.logdebug("Details: %s", target.wait)
        exit_status = target.wait.exit_status
        if exit_status != 0:
            msg = ("Target container %s wait command, non-zero exit(%d), "
                   "see debuglog for details"
                   % (target.name, exit_status))
            self.logwarning(msg)
            self.logdebug(str(target.wait))

    def postprocess(self):
        super(WaitBase, self).postprocess()
        for target in self.sub_stuff['targets']:
            self.pproc_target_waits(target)
        for target, dkrcmd in self.sub_stuff['targets'].iteritems():
            self.pproc_target(target, dkrcmd)
        if self.config['wait_verbose']:
            self.logdebug("Details of wait command: %s",
                          self.sub_stuff['dkrcmd'])
        self.pproc_outputgood()
        self.pproc_exit()
        self.pproc_stdio('stderr')
        self.pproc_stdio('stdout')

    def cleanup(self):
        super(WaitBase, self).cleanup()
        sss = self.sub_stuff
        self.sub_stuff['dc'].clean_all([target.name
                                        for target in sss['targets']])


# Generate any generic sub-subtests not found in this or other modules
def generic_factory(name):

    class Generic(WaitBase):
        pass

    Generic.__name__ = name
    return Generic

subname = 'docker_cli/wait'
config = Config()
subsubnames = get_as_list(config[subname]['subsubtests'])
ssconfigs = []
globes = globals()
for ssname in subsubnames:
    if ssname not in globes:
        cls = generic_factory(ssname)
        # Inject generated class into THIS module's namespace
        globes[cls.__name__] = cls
