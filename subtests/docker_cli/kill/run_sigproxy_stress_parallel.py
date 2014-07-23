"""
Sigproxy stress test
"""
from dockertest.dockercmd import DockerCmd
from parallel_stress import parallel_stress


class run_sigproxy_stress_parallel(parallel_stress):

    """
    Tests handling of docker run --sig-proxy=true (lots of parallel kills)

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
        """
        Generates signals_set and kill_cmds pseudo-randomly
        """
        signals = [int(sig) for sig in self.config['kill_signals'].split()]
        signals = range(*signals)   # unknown config args pylint: disable=W0142
        for noncatchable_signal in (9, 17):
            try:
                signals.remove(noncatchable_signal)
            except ValueError:
                pass
        cont_pid = self.sub_stuff['container_cmd'].process_id
        cmds = []
        for signal in signals:
            cmd = ("while [ -e %s/docker_kill_stress ]; "
                   "do kill -s %s %s || exit 255; done"
                   % (self.tmpdir, signal, cont_pid))
            cmds.append(cmd)
        self.sub_stuff['kill_cmds'] = cmds

        # SIGCONT after the test finishes (to resume possibly stopped container
        self.sub_stuff['cont_docker'] = DockerCmd(self, 'kill',
                                                  ['-s 18'] + extra_subargs,
                                                  verbose=False)

        signals.remove(19)  # SIGSTOP is also not catchable
        self.sub_stuff['signals_set'] = signals

        # kill -9
        self.sub_stuff['kill_docker'] = DockerCmd(self, 'kill', extra_subargs,
                                                  verbose=False)
