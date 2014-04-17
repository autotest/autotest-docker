"""
Test usage of docker 'kill' command

initialize:
1) start VM with test command
run_once:
2) execute docker kill
postprocess:
3) analyze results
"""
import itertools
import random
import time

from autotest.client import utils
from autotest.client.shared.utils import wait_for
from dockertest import config, subtest, xceptions
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd, NoFailDockerCmd
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.subtest import SubSubtest


# TODO: Not all named signals seems to be supported with docker0.9
SIGNAL_MAP = {1: 'HUP', 2: 'INT', 3: 'QUIT', 4: 'ILL', 5: 'TRAP', 6: 'ABRT',
              7: 'BUS', 8: 'FPE', 9: 'KILL', 10: 'USR1', 11: 'SEGV',
              12: 'USR2', 13: 'PIPE', 14: 'ALRM', 15: 'TERM', 16: 'STKFLT',
              17: 'CHLD', 18: 'CONT', 19: 'STOP', 20: 'TSTP', 21: 'TTIN',
              22: 'TTOU', 23: 'URG', 24: 'XCPU', 25: 'XFSZ', 26: 'VTALRM',
              27: 'PROF', 28: 'WINCH', 29: 'IO', 30: 'PWR', 31: 'SYS'}


# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103
class kill(subtest.SubSubtestCaller):

    """ Subtest caller """
    config_section = 'docker_cli/kill'


class kill_base(SubSubtest):

    """ Base class """

    def initialize(self):
        super(kill_base, self).initialize()
        # Prepare a container
        docker_containers = DockerContainers(self.parent_subtest)
        prefix = self.config["kill_name_prefix"]
        name = docker_containers.get_unique_name(prefix, length=4)
        self.sub_stuff['container_name'] = name
        config.none_if_empty(self.config)
        if self.config.get('run_options_csv'):
            subargs = [arg for arg in
                       self.config['run_options_csv'].split(',')]
        else:
            subargs = []
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append("bash")
        subargs.append("-c")
        subargs.append(self.config['exec_cmd'])
        container = AsyncDockerCmd(self.parent_subtest, 'run', subargs)
        self.sub_stuff['container_cmd'] = container
        container.execute()
        time.sleep(self.config['wait_start'])

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
            for noncatchable_signals in (9, 17):
                try:
                    signals.remove(noncatchable_signals)
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
        sequence = self._create_kill_sequence()
        signals_sequence = []
        kill_cmds = []
        mapped = False
        sig_long = False
        for item in sequence:
            if item == "M":
                mapped = True
            elif item == "L":
                sig_long = True
            else:
                signal = int(item)
                signals_sequence.append(signal)
                if mapped:
                    signal = SIGNAL_MAP.get(signal, signal)
                    mapped = False
                if sig_long:
                    subargs = ["--signal=%s" % signal] + extra_subargs
                    sig_long = False
                else:
                    subargs = ["-s %s" % signal] + extra_subargs
                kill_cmds.append(DockerCmd(self.parent_subtest,
                                           'kill',
                                           subargs))

        # Kill -9 is the last one :-)
        signal = 9
        signals_sequence.append(signal)
        if self.config.get('kill_map_signals'):
            signal = SIGNAL_MAP.get(signal, signal)
        kill_cmds.append(DockerCmd(self.parent_subtest, 'kill',
                                   ["-s %s" % signal] + extra_subargs))

        self.logdebug("kill_command_example: %s", kill_cmds[0])
        self.logdebug("signals_sequence: %s", " ".join(sequence))
        self.sub_stuff['signals_sequence'] = signals_sequence
        self.sub_stuff['kill_cmds'] = kill_cmds

    def postprocess(self):
        super(kill_base, self).postprocess()
        for kill_result in self.sub_stuff.get('kill_results', []):
            OutputGood(kill_result)
            self.failif(kill_result.exit_status != 0, "Exit status of the %s "
                        "command was not 0 (%s)"
                        % (kill_result.command, kill_result.exit_status))
        if 'container_results' in self.sub_stuff:
            OutputGood(self.sub_stuff['container_results'])
            self.failif(self.sub_stuff['container_results'].exit_status != 255,
                        "Exit status of the docker run command wasn't 255 (%s)"
                        % self.sub_stuff['container_results'].exit_status)

    def pre_cleanup(self):
        pass

    def container_cleanup(self):
        if self.sub_stuff.get('container_name') is None:
            return  # Docker was not created, we are clean
        containers = DockerContainers(self.parent_subtest)
        name = self.sub_stuff['container_name']
        conts = containers.list_containers_with_name(name)
        if conts == []:
            return  # Docker was created, but apparently doesn't exist, clean
        elif len(conts) > 1:
            msg = ("Multiple containers matches name %s, not removing any of "
                   "them...", name)
            raise xceptions.DockerTestError(msg)
        NoFailDockerCmd(self.parent_subtest, 'rm', ['--force', '--volumes',
                                                    name]).execute()

    def cleanup(self):
        super(kill_base, self).cleanup()
        cleanup_log = []
        for method in ('pre_cleanup', 'container_cleanup'):
            try:
                getattr(self, method)()
            except Exception, details:
                cleanup_log.append("%s failed: %s" % (method, details))
        if cleanup_log:
            msg = "Cleanup failed:\n%s" % "\n".join(cleanup_log)
            self.logerror(msg)  # message is not logged nicely in exc
            raise xceptions.DockerTestError(msg)


class kill_check_base(kill_base):

    """ Base class for signal-check based tests """

    def run_once(self):
        class Output:

            def __init__(self, container):
                self.container = container
                self.idx = len(container.stdout)

            def get(self, idx=None):
                if idx is None:
                    idx = self.idx
                out = container_cmd.stdout.splitlines()
                self.idx = len(out)
                return out[idx:]
        # Execute the kill command
        super(kill_check_base, self).run_once()
        container_cmd = self.sub_stuff['container_cmd']
        container_out = Output(container_cmd)
        kill_cmds = self.sub_stuff['kill_cmds']
        signals_sequence = self.sub_stuff['signals_sequence']
        _check = self.config['check_stdout']
        timeout = self.config['stress_cmd_timeout']
        self.sub_stuff['kill_results'] = []
        stopped_log = False
        for cmd, signal in itertools.izip(kill_cmds, signals_sequence):
            result = cmd.execute()
            if signal == -1:
                if result.exit_status == 0:    # Any bad signal
                    msg = ("Kill command %s returned zero status when using "
                           " bad signal."
                           % (self.sub_stuff['kill_results'][-1].command))
                    raise xceptions.DockerTestFail(msg)
                continue
            self.sub_stuff['kill_results'].append(result)
            if result.exit_status != 0:
                msg = ("Kill command %s returned non-zero status. (%s)"
                       % (self.sub_stuff['kill_results'][-1].command,
                          self.sub_stuff['kill_results'][-1].exit_status))
                raise xceptions.DockerTestFail(msg)
            if signal == 9 or signal is None:   # SIGTERM
                for _ in xrange(50):
                    if container_cmd.done:
                        break
                    time.sleep(0.1)
                else:
                    raise xceptions.DockerTestFail("Container process did not"
                                                   " finish when kill -9 "
                                                   "was executed.")
                self.sub_stuff['container_results'] = container_cmd.wait()
            elif signal == 19:    # SIGSTOP can't be cought
                if stopped_log is False:
                    stopped_log = set()
            elif signal == 18:  # SIGCONT, check previous payload
                # TODO: Signals 20, 21 and 22 are not reported after SIGCONT
                #       even thought they are reported when docker is not
                #       stopped.
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
                        msg = ("Check line not in docker output, signal "
                               "was probably not passed/handled properly."
                               "\nmissing: %s\nstopped_log: %s\n"
                               "docker_output: %s"
                               % (line, stopped_log, container_out.get(_idx)))
                        raise xceptions.DockerTestFail(msg)
                stopped_log = False
            elif stopped_log is not False:  # if not false it's set()
                stopped_log.add(signal)
            else:
                _idx = container_out.idx
                check = _check % signal
                output_matches = lambda: check in container_out.get(_idx)
                # Wait until the signal gets logged
                if wait_for(output_matches, timeout, step=0) is None:
                    msg = ("Check line not in docker output, signal was "
                           "probably not passed/handled properly.\n"
                           "check: %s\noutput:%s"
                           % (check, container_out.get(_idx)))
                    raise xceptions.DockerTestFail(msg)


class random_num(kill_check_base):

    """
    Test usage of docker 'kill' command (series of random valid numeric
    signals)

    initialize:
    1) start VM with test command
    2) create random sequence of kill signals
    run_once:
    3) execute series of kill signals (NUMERIC) followed with the output check
    3b) in case of SIGSTOP it stores following signals until SIGCONT and
        verifies they were all handled properly
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """
    pass


class random_name(kill_check_base):

    """
    Test usage of docker 'kill' command (series of random correctly named
    signals)

    initialize:
    1) start VM with test command
    2) create random sequence of kill signals
    run_once:
    3) execute series of kill signals (NAME) followed with the output check
    3b) in case of SIGSTOP it stores following signals until SIGCONT and
        verifies they were all handled properly
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """
    pass


class sigstop(kill_check_base):

    """
    Test usage of docker 'kill' command (stopped container)

    initialize:
    1) start VM with test command
    2) create sequence of signals in this manner (uses numeric values):
       [SIGSTOP, 1, 2, 3, .., 8, 10, .., 16, SIGSTOP, 20, .., 31, SIGCONT, 9]
    run_once:
    3) execute series of kill signals followed with the output check
    3b) in case of SIGSTOP it stores following signals until SIGCONT and
        verifies they were all handled properly
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """

    def _populate_kill_cmds(self, extra_subargs):
        signals_sequence = range(1, 32)
        signals_sequence.remove(9)
        signals_sequence.remove(17)
        signals_sequence.remove(18)

        # TODO: Should these be ignored? They can be caught when not STOPPED
        # signals_sequence.remove(20)
        # signals_sequence.remove(21)
        # signals_sequence.remove(22)

        signals_sequence = [19] + signals_sequence + [18, 9]
        kill_cmds = []
        for signal in signals_sequence:
            subargs = (["%s%s" % (random.choice(('-s ', '--signal=')), signal)]
                       + extra_subargs)
            kill_cmds.append(DockerCmd(self.parent_subtest, 'kill', subargs))

        self.logdebug("kill_command_example: %s", kill_cmds[0])
        self.logdebug("signals_sequence: %s", signals_sequence)
        self.sub_stuff['signals_sequence'] = signals_sequence
        self.sub_stuff['kill_cmds'] = kill_cmds


class bad(kill_check_base):

    """
    Test usage of docker 'kill' command (bad signals)

    initialize:
    1) start VM with test command
    2) create sequence of signals, where first and last ones are correct,
       other signals are mix of various incorrect names and values.
    run_once:
    3) execute series of kill signals followed with the output check
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """

    def _populate_kill_cmds(self, extra_subargs):
        # TODO: 0 is accepted even thought it's bad signal
        signals_sequence = ['USR1', 0, -1, -random.randint(2, 32767),
                            random.randint(32, 63), random.randint(64, 32767),
                            "SIGBADSIGNAL", "SIG", "%", "!", "\\", '', "''",
                            '""', ' ', 'USR1']
        signals_sequence = signals_sequence + [9]
        kill_cmds = []
        for signal in signals_sequence:
            subargs = (["%s%s" % (random.choice(('-s ', '--signal=')), signal)]
                       + extra_subargs)
            kill_cmds.append(DockerCmd(self.parent_subtest, 'kill', subargs))

        # Change signals_sequence into results-like numbers
        # -1 => incorrect signal, otherwise signal number
        signals_sequence = [-1] * len(signals_sequence)
        signals_sequence[0] = 10
        signals_sequence[-2] = 10
        signals_sequence[-1] = 9
        self.logdebug("kill_command_example: %s", kill_cmds[0])
        self.logdebug("signals_sequence: %s", signals_sequence)
        self.sub_stuff['signals_sequence'] = signals_sequence
        self.sub_stuff['kill_cmds'] = kill_cmds


class stress(kill_base):

    """
    Test usage of docker 'kill' command (lots of various kills and then check)

    initialize:
    1) start VM with test command
    2) create sequence of signals and prepare bash script, which executes them
       quickly one by one.
    run_once:
    3) executes the bash script, which executes series of kills quickly.
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """

    def _populate_kill_cmds(self, extra_subargs):
        sequence = self._create_kill_sequence()
        signals_set = set()
        signals_sequence = []
        stopped = False
        mapped = False
        for item in sequence:
            if item == "M":
                mapped = True
            elif item == "L":   # Long is ignored in this test
                pass
            else:
                signal = int(item)
                if signal == 18:
                    if stopped:
                        signals_set.add(stopped)
                    stopped = False
                    signals_set.add(signal)
                elif signal == 19:
                    stopped = set()
                else:
                    signals_set.add(str(signal))
                if mapped:
                    signal = SIGNAL_MAP.get(signal, signal)
                    mapped = False
                signals_sequence.append(str(signal))

        subargs = ["-s $SIGNAL"] + extra_subargs
        docker_cmd = DockerCmd(self.parent_subtest, 'kill', subargs)
        cmd = ("for SIGNAL in %s; do %s || exit 255; done"
               % (" ".join(signals_sequence), docker_cmd.command))
        self.sub_stuff['kill_cmds'] = [cmd]
        # kill -9
        self.sub_stuff['kill_cmds'].append(DockerCmd(self.parent_subtest,
                                                     'kill', extra_subargs))
        self.sub_stuff['signals_set'] = signals_set

        self.logdebug("kill_command: %s", cmd)
        self.logdebug("signals_sequence: %s", " ".join(sequence))

    def run_once(self):
        # Execute the kill command
        super(stress, self).run_once()
        container_cmd = self.sub_stuff['container_cmd']
        kill_cmds = self.sub_stuff['kill_cmds']
        signals_set = self.sub_stuff['signals_set']
        timeout = self.config['stress_cmd_timeout']
        _check = self.config['check_stdout']
        self.sub_stuff['kill_results'] = [utils.run(kill_cmds[0],
                                                    verbose=True)]
        endtime = time.time() + timeout
        line = None
        out = None
        while endtime > time.time():
            try:
                out = container_cmd.stdout.splitlines()
                for line in [_check % sig for sig in signals_set]:
                    out.remove(line)
                break
            except ValueError:
                pass
        else:
            msg = ("Check line not in docker output, signal "
                   "was probably not passed/handled properly."
                   "\nmissing: %s\nexpected_signals: %s\n"
                   "docker_output: %s"
                   % (line, signals_set, container_cmd.stdout))
            raise xceptions.DockerTestFail(msg)
        # Kill -9
        self.sub_stuff['kill_results'].append(kill_cmds[1].execute())
        for _ in xrange(50):
            if container_cmd.done:
                break
            time.sleep(0.1)
        else:
            raise xceptions.DockerTestFail("Container process did not"
                                           " finish when kill -9 "
                                           "was executed.")
        self.sub_stuff['container_results'] = container_cmd.wait()


class parallel_stress(kill_base):

    """
    Test usage of docker 'kill' command (simultaneous kills)

    initialize:
    1) start VM with test command
    2) creates command for each signal, which kills the docker in a loop
    run_once:
    3) executes all the kill scripts to run in parallel
    4) stops the kill scripts
    5) sends docker kill -9 and verifies docker was killed
    postprocess:
    6) analyze results
    """

    def _populate_kill_cmds(self, extra_subargs):
        signals = [int(sig) for sig in self.config['kill_signals'].split()]
        signals = range(*signals)
        for noncatchable_signal in (9, 17):
            try:
                signals.remove(noncatchable_signal)
            except ValueError:
                pass

        cmds = []
        for signal in signals:
            subargs = ["-s %s" % signal] + extra_subargs
            docker_cmd = DockerCmd(self.parent_subtest, 'kill', subargs)
            cmd = ("while [ -e /var/tmp/docker_kill_stress ]; "
                   "do %s || exit 255; done" % docker_cmd.command)
            cmds.append(cmd)
        self.sub_stuff['kill_cmds'] = cmds

        signals.remove(19)  # SIGSTOP is also not catchable
        self.sub_stuff['signals_set'] = signals

        # kill -9
        self.sub_stuff['kill_docker'] = DockerCmd(self.parent_subtest, 'kill',
                                                  extra_subargs)

    def run_once(self):
        # Execute the kill command
        super(parallel_stress, self).run_once()
        container_cmd = self.sub_stuff['container_cmd']
        kill_cmds = self.sub_stuff['kill_cmds']
        signals_set = self.sub_stuff['signals_set']
        _check = self.config['check_stdout']

        # Enable stress loops
        self.sub_stuff['touch_result'] = utils.run("touch /var/tmp/"
                                                   "docker_kill_stress")
        # Execute stress loops
        self.sub_stuff['kill_jobs'] = []
        for cmd in kill_cmds:
            job = utils.AsyncJob(cmd, verbose=True)
            self.sub_stuff['kill_jobs'].append(job)

        # Wait test_length (while checking for failures)
        endtime = time.time() + self.config['test_length']
        while endtime > time.time():
            for job in self.sub_stuff['kill_jobs']:
                if job.sp.poll() is not None:   # process finished
                    for job in self.sub_stuff.get('kill_jobs', []):
                        self.logerror("cmd %s (%s)", job.command,
                                      job.sp.poll())
                    out = utils.run("ls /var/tmp/docker_kill_stress",
                                    ignore_status=True).exit_status
                    self.logerror("ls /var/tmp/docker_kill_stress (%s)", out)
                    raise xceptions.DockerTestFail("stress command finished "
                                                   "unexpectedly, see log for "
                                                   "details.")

        # Stop stressers
        cmd = "rm -f /var/tmp/docker_kill_stress"
        self.sub_stuff['rm_result'] = utils.run(cmd)

        self.sub_stuff['kill_results'] = []
        for job in self.sub_stuff['kill_jobs']:
            try:
                self.sub_stuff['kill_results'].append(job.wait_for(5))
            except Exception, details:
                self.logerror("Job %s did not finish: %s", job.command,
                              str(details))
        del self.sub_stuff['kill_jobs']

        # Check the output
        endtime = time.time() + self.config['stress_cmd_timeout']
        line = None
        out = None
        while endtime > time.time():
            try:
                out = container_cmd.stdout.splitlines()
                for line in [_check % sig for sig in signals_set]:
                    out.remove(line)
                break
            except ValueError:
                pass
        else:
            msg = ("Check line not in docker output, signal "
                   "was probably not passed/handled properly."
                   "\nmissing: %s\nexpected_signals: %s\n"
                   "docker_output: %s"
                   % (line, signals_set, container_cmd.stdout))
            raise xceptions.DockerTestFail(msg)

        # Kill -9
        cmd = self.sub_stuff['kill_docker']
        self.sub_stuff['kill_results'].append(cmd.execute())
        for _ in xrange(50):
            if container_cmd.done:
                break
            time.sleep(0.1)
        else:
            raise xceptions.DockerTestFail("Container process did not"
                                           " finish when kill -9 "
                                           "was executed.")
        self.sub_stuff['container_results'] = container_cmd.wait()

    def pre_cleanup(self):
        if not self.sub_stuff.get('rm_result'):
            utils.run("rm -f /var/tmp/docker_kill_stress", ignore_status=True)
            for job in self.sub_stuff.get('kill_jobs', []):
                try:
                    job.wait_for(5)     # AsyncJob destroys it on timeout
                except Exception, details:
                    msg = ("Job %s did not finish: %s" % (job.command,
                                                          details))
                    raise xceptions.DockerTestFail(msg)
        for result in ('touch_result', 'rm_result'):
            if result in self.sub_stuff:
                result = self.sub_stuff[result]
                self.failif(result.exit_status != 0,
                            "Exit status of the %s command was not 0 (%s)"
                            % (result.command, result.exit_status))
