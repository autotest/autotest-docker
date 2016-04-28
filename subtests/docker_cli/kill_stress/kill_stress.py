"""
Summary
-------

Sends signals to container very quickly

Operational Summary
-------------------

1. start container with test command
2. execute ``docker kill`` (or kill $PID) for each signal in
   ``signals_sequence`` one after another without delay (using bash for loop)
3. analyze results
"""
import os
import time

from autotest.client import utils
from dockertest import xceptions, subtest
from dockertest.dockercmd import DockerCmd
from kill_utils import kill_base, SIGNAL_MAP, Output


class kill_stress(subtest.SubSubtestCaller):

    """ Subtest caller """


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
    @staticmethod
    def _map_sequence_to_signals(sequence):
        """
        Analyzes given sequence and fills signals_sequence and set.
        :param sequence: string defining the signals
        :return: tuple(signals_sequence, signals_set)
                 signals_sequence = sequence of signals (ints)
                 signals_set = set of signals, which should be present in the
                               output.
        """
        stopped = False
        mapped = False
        signals_set = set()
        signals_sequence = []
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
        return signals_sequence, signals_set

    def _populate_kill_cmds(self, extra_subargs):
        sequence = self._create_kill_sequence()
        sigproxy = self.config.get('kill_sigproxy')
        signals_sequence, signals_set = self._map_sequence_to_signals(sequence)

        subargs = ["-s $SIGNAL"] + extra_subargs
        if sigproxy:
            pid = self.sub_stuff['container_cmd'].process_id
            cmd = "kill -$SIGNAL %s" % pid
        else:
            cmd = DockerCmd(self, 'kill', subargs).command
        cmd = ("for SIGNAL in %s; do %s || exit 255; done"
               % (" ".join(signals_sequence), cmd))
        self.sub_stuff['kill_cmds'] = [cmd]
        # kill -9
        if sigproxy:
            self.sub_stuff['kill_cmds'].append(False)
        else:
            dcmd = DockerCmd(self, 'kill', extra_subargs)
            self.sub_stuff['kill_cmds'].append(dcmd)
        self.sub_stuff['signals_set'] = signals_set

        self.logdebug("kill_command: %s", cmd)
        self.logdebug("signals_sequence: %s", " ".join(sequence))

    def run_once(self):
        # Execute the kill command
        kill_base.run_once(self)
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
            self.fail_missing(_check, signals_set, Output(container_cmd, 0),
                              line)
        # Kill -9
        if kill_cmds[1] is not False:   # Custom kill command
            self.sub_stuff['kill_results'].append(kill_cmds[1].execute())
        else:   # kill the container process
            os.kill(container_cmd.process_id, 9)
        for _ in xrange(50):
            if container_cmd.done:
                break
            time.sleep(0.1)
        else:
            raise xceptions.DockerTestFail("Container process did not"
                                           " finish when kill -9 "
                                           "was executed.")
        self.sub_stuff['container_results'] = container_cmd.wait()


class stress_ttyoff(stress):

    """ Non-tty variant of the stress test """
    tty = False


class run_sigproxy_stress_ttyoff(stress):

    """ non-tty variant of the run_sigproxy_stress test """
    tty = False


class attach_sigproxy_stress_ttyoff(stress):

    """ non-tty variant of the attach_sigproxy_stress test """
    tty = False
