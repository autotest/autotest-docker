import random

from dockertest.dockercmd import DockerCmd
from kill import kill_check_base


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
            kill_cmds.append(DockerCmd(self.parent_subtest, 'kill', subargs,
                             verbose=False))

        self.logdebug("kill_command_example: %s", kill_cmds[0])
        self.logdebug("signals_sequence: %s", signals_sequence)
        self.sub_stuff['signals_sequence'] = signals_sequence
        self.sub_stuff['kill_cmds'] = kill_cmds
