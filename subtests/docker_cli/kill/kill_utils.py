"""
Utils for ``docker kill`` related tests.
:warning: Keep all of these in sync; currently known users:
          ``kill,kill_stopped,kill_stress,kill_parallel_stress``
"""

# This library is symlinked for use by several subtests which
# should eventually be combined.  Ignore unused imports errors for now:
# pylint: disable=W0611

import itertools
import os
import random
import time
from autotest.client.shared.utils import wait_for
from dockertest import config, subtest, xceptions
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest.images import DockerImages
from dockertest.output import OutputGood, mustpass
from dockertest.images import DockerImage


SIGNAL_MAP = {1: 'HUP', 2: 'INT', 3: 'QUIT', 4: 'ILL', 5: 'TRAP', 6: 'ABRT',
              7: 'BUS', 8: 'FPE', 9: 'KILL', 10: 'USR1', 11: 'SEGV',
              12: 'USR2', 13: 'PIPE', 14: 'ALRM', 15: 'TERM', 16: 'STKFLT',
              17: 'CHLD', 18: 'CONT', 19: 'STOP', 20: 'TSTP', 21: 'TTIN',
              22: 'TTOU', 23: 'URG', 24: 'XCPU', 25: 'XFSZ', 26: 'VTALRM',
              27: 'PROF', 28: 'WINCH', 29: 'IO', 30: 'PWR', 31: 'SYS'}


class Output(object):   # only containment pylint: disable=R0903

    """
    Wraps object with `.stdout` method and returns only new chars out of it
    """

    def __init__(self, stuff, idx=None):
        self.stuff = stuff
        if idx is None:
            self.idx = len(stuff.stdout.splitlines())
        else:
            self.idx = idx

    def get(self, idx=None):
        """
        :param idx: Override last index
        :return: Output of stuff.stdout from idx (or last read)
        """
        if idx is None:
            idx = self.idx
        out = self.stuff.stdout.splitlines()
        self.idx = len(out)
        print ">>> got here: idx=%d -> %d : '%s'" % (idx, self.idx, out[idx:])
        return out[idx:]


class kill_base(subtest.SubSubtest):

    """ Base class """

    # By default use tty. In the end generate the same class without tty
    tty = True

    def _init_container_normal(self, name):
        """
        Starts container
        """
        if self.config.get('run_options_csv'):
            subargs = [arg for arg in
                       self.config['run_options_csv'].split(',')]
        else:
            subargs = []
        if self.tty:
            subargs.append('--tty=true')
        else:
            subargs.append('--tty=false')
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append("bash")
        subargs.append("-c")
        subargs.append(self.config['exec_cmd'])
        container = AsyncDockerCmd(self, 'run', subargs)
        self.sub_stuff['container_cmd'] = container
        container.execute()

    def _init_container_attached(self, name):
        """
        Starts detached container and attaches it using docker attach
        """
        if self.config.get('run_options_csv'):
            subargs = [arg for arg in
                       self.config['run_options_csv'].split(',')]
        else:
            subargs = []
        if self.tty:
            subargs.append('--tty=true')
        else:
            subargs.append('--tty=false')
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append("bash")
        subargs.append("-c")
        subargs.append(self.config['exec_cmd'])
        container = DockerCmd(self, 'run', subargs)
        self.sub_stuff['container_cmd'] = container
        mustpass(container.execute())

        if self.config.get('attach_options_csv'):
            subargs = [arg for arg in
                       self.config['attach_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append(name)
        c_attach = AsyncDockerCmd(self, 'attach', subargs)
        self.sub_stuff['container_cmd'] = c_attach  # overwrites finished cmd
        c_attach.execute()

    def initialize(self):
        super(kill_base, self).initialize()
        # Prepare a container
        docker_containers = DockerContainers(self)
        name = docker_containers.get_unique_name("test", length=4)
        self.sub_stuff['container_name'] = name
        config.none_if_empty(self.config)
        if self.config.get('run_container_attached'):
            self._init_container_attached(name)
        else:
            self._init_container_normal(name)

        cmd = self.sub_stuff['container_cmd']
        cmd.wait_for_ready()

        # Prepare the "kill" command
        if self.config.get('kill_options_csv'):
            subargs = [arg for arg in
                       self.config['kill_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append(name)
        self._populate_kill_cmds(subargs)

    def _create_kill_sequence(self):
        """
        Creates/loads the kill number sequence. Format of this sequence is
        [$MAP] [$LONG] $SIG_NUM ... (eg. 2 M 23 22 M L 12 1 M 27)
        MAP => map the signal number to symbolic name
        LONG => use --signal= (instead of -s)
        """
        map_signals = self.config.get('kill_map_signals')
        if not self.config.get('signals_sequence'):
            sequence = []
            signals = [int(sig) for sig in self.config['kill_signals'].split()]
            signals = range(*signals)
            skipped_signals = (int(_) for _ in
                               self.config.get('skip_signals', "").split())
            for skipped_signal in skipped_signals:
                try:
                    signals.remove(skipped_signal)
                except ValueError:
                    pass
            for _ in xrange(self.config['no_iterations']):
                if (map_signals is True or (map_signals is None and
                                            random.choice((True, False)))):
                    sequence.append("M")    # mapped signal (USR1)
                if random.choice((True, False)):
                    sequence.append("L")    # long cmd (--signal=)
                sequence.append(str(random.choice(signals)))
        else:
            sequence = self.config['signals_sequence'].split()
        return sequence

    def _populate_kill_cmds(self, extra_subargs):
        """
        Populates variables according to sequence
        """
        sequence = self._create_kill_sequence()
        signals_sequence = []
        kill_cmds = []
        mapped = False
        sig_long = False
        sigproxy = self.config.get('kill_sigproxy')
        for item in sequence:
            if item == "M":
                mapped = True
            elif item == "L":
                sig_long = True
            else:
                signal = int(item)
                signals_sequence.append(signal)
                if sigproxy:
                    kill_cmds.append(False)     # False => kill the docker_cmd
                    continue
                if mapped:
                    signal = SIGNAL_MAP.get(signal, signal)
                    mapped = False
                if sig_long:
                    subargs = ["--signal=%s" % signal] + extra_subargs
                    sig_long = False
                else:
                    subargs = ["-s %s" % signal] + extra_subargs
                kill_cmds.append(DockerCmd(self, 'kill', subargs))

        # Kill -9 is the last one :-)
        signal = 9
        signals_sequence.append(signal)
        if self.config.get('kill_map_signals'):
            signal = SIGNAL_MAP.get(signal, signal)
        kill_cmds.append(DockerCmd(self, 'kill',
                                   ["-s %s" % signal] + extra_subargs))

        if sigproxy:
            self.logdebug("kill_command_example: Killing directly the "
                          "container process.")
        else:
            self.logdebug("kill_command_example: %s", kill_cmds[0])
        self.logdebug("signals_sequence: %s", " ".join(sequence))
        self.sub_stuff['signals_sequence'] = signals_sequence
        self.sub_stuff['kill_cmds'] = kill_cmds

    def fail_missing(self, check, stopped_log, container_out, line):
        """Expected signal missing, log details, fail the test"""
        idx = container_out.idx
        msg = ("Not all signals were handled inside container "
               "after SIGCONT execution.\nExpected output "
               "(unordered):\n  %s\nActual container output:\n"
               "  %s\nFirst missing line:\n  %s"
               % ("\n  ".join([check % sig for sig in stopped_log]),
                  "\n  ".join(container_out.get(idx)), line))
        self.logdebug(msg)
        raise xceptions.DockerTestFail("Missing Signal(s), see debug "
                                       "log for more details.")

    def postprocess(self):
        super(kill_base, self).postprocess()
        for kill_result in self.sub_stuff.get('kill_results', []):
            OutputGood(kill_result)
            self.failif_ne(kill_result.exit_status, 0,
                           "Exit status of %s command" % kill_result.command)

    def cleanup(self):
        super(kill_base, self).cleanup()
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            dc.clean_all([self.sub_stuff.get("container_name")])


class kill_check_base(kill_base):

    """ Base class for signal-check based tests """

    def _execute_command(self, cmd, signal, _container_pid):
        """
        Execute cmd and verify it was executed properly
        :param cmd: DockerCmd or False to send signal directly
        """
        if cmd is not False:    # Custom command, execute&check cmd status
            result = cmd.execute()
            self.sub_stuff['kill_results'].append(result)
            if signal == -1:
                if result.exit_status == 0:    # Any bad signal
                    msg = ("Kill command %s returned zero status when "
                           "using bad signal."
                           % (self.sub_stuff['kill_results'][-1].command))
                    raise xceptions.DockerTestFail(msg)
            else:
                if result.exit_status != 0:
                    msg = ("Kill command %s returned non-zero status. (%s)"
                           % (self.sub_stuff['kill_results'][-1].command,
                              self.sub_stuff['kill_results'][-1].exit_status))
                    raise xceptions.DockerTestFail(msg)
        else:   # Send signal directly to the docker process
            self.logdebug("Sending signal %s directly to container pid %s",
                          signal, _container_pid)
            os.kill(_container_pid, signal)

    def _kill_dash_nine(self, container_cmd):
        """
        Destroy the container with -9, check that it died in 5s
        """
        for _ in xrange(50):    # wait for command to finish
            if container_cmd.done:
                break
            time.sleep(0.1)
        else:
            raise xceptions.DockerTestFail("Container process did not"
                                           " finish when kill -9 "
                                           "was executed.")
        self.sub_stuff['container_results'] = container_cmd.wait()

    def _check_previous_payload(self, stopped_log, container_out,
                                timeout, _check):
        """
        Checks that all signals from stopped_log are present in container_out
        """
        if stopped_log:
            endtime = time.time() + timeout
            _idx = container_out.idx
            line = None
            out = None
            while endtime > time.time():
                try:
                    out = container_out.get(_idx)
                    for line in [_check % sig for sig in stopped_log]:
                        out.remove(line)
                    break
                except ValueError:
                    pass
            else:
                self.fail_missing(_check, stopped_log, container_out, line)

    def _check_signal(self, container_out, _check, signal, timeout):
        """
        Check container for $signal check output presence
        """
        _idx = container_out.idx
        check = _check % signal
        output_matches = lambda: check in container_out.get(_idx)
        # Wait until the signal gets logged
        if wait_for(output_matches, timeout, step=0.1) is None:
            msg = ("Signal %s not handled inside container.\nExpected "
                   "output:\n  %s\nActual container output:\n  %s"
                   % (signal, check,
                      "\n  ".join(container_out.get(_idx))))
            self.logdebug(msg)
            # FIXME: run 'docker logs container_id' here
            raise xceptions.DockerTestFail("Unhandled signal(s), see debug"
                                           "log for more details")

    def run_once(self):
        # Execute the kill command
        super(kill_check_base, self).run_once()
        container_cmd = self.sub_stuff['container_cmd']
        container_out = Output(container_cmd)
        kill_cmds = self.sub_stuff['kill_cmds']
        signals_sequence = self.sub_stuff['signals_sequence']
        _check = self.config['check_stdout']
        timeout = self.config['stress_cmd_timeout']
        self.sub_stuff['kill_results'] = []
        stopped_log = None
        _container_pid = container_cmd.process_id
        self.loginfo("Running kill sequence...")
        for cmd, signal in itertools.izip(kill_cmds, signals_sequence):
            self._execute_command(cmd, signal, _container_pid)
            if signal == -1:    # Bad signal, no other checks
                continue
            elif signal == 9 or signal is None:   # SIGTERM
                self._kill_dash_nine(container_cmd)
            elif signal == 19:    # SIGSTOP can't be caught
                if stopped_log is None:
                    stopped_log = set()
            elif signal == 18:  # SIGCONT, check previous payload
                self._check_previous_payload(stopped_log, container_out,
                                             timeout, _check)
                stopped_log = None
            elif stopped_log is not None:  # if not false it's set()
                if cmd is not False:
                    # Using docker kill: signals are forwarded when the cont
                    #                    is ready
                    # disable E1101, when stopped_log is not False, it's []
                    stopped_log.add(signal)  # pylint: disable=E1101
                # else: using proxy:  signals are not forwarded by proxy, when
                #                     proxy is SIGSTOPped.
            else:   # normal signal should be logged in container
                self._check_signal(container_out, _check, signal, timeout)
