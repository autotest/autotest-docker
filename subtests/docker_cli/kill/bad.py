"""
Bad signals test
"""
import random
from kill import kill_check_base, QDockerCmd


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
        if self.config.get('signals_sequence'):
            signals_sequence = self.config.get('signals_sequence').split(',')
        else:
            signals_sequence = ['USR1', 0, -1, -random.randint(2, 32767),
                                random.randint(32, 63),
                                random.randint(64, 32767), "SIGBADSIGNAL",
                                "SIG", "%", "!", "\\", '', "''", '""', ' ',
                                'USR1']
        signals_sequence.append(9)
        kill_cmds = []
        for signal in signals_sequence:
            subargs = (["%s%s" % (random.choice(('-s ', '--signal=')), signal)]
                       + extra_subargs)
            dc = QDockerCmd(self.parent_subtest, 'kill', subargs)
            kill_cmds.append(dc)

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
