"""
Summary
-------

Sends signals to container very quickly in parallel (one process per signal)

Operational Summary
-------------------

#. start container with test command
#. spawn one worker per each signal and let them stress container for
   ``test_time``.
#. analyze results
"""
import time

from autotest.client import utils
from dockertest import subtest, xceptions
from dockertest.dockercmd import DockerCmd
from kill_utils import kill_base, Output


class kill_parallel_stress(subtest.SubSubtestCaller):

    """ Subtest caller """


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

        cmds = []
        for signal in signals:
            subargs = ["-s %s" % signal] + extra_subargs
            docker_cmd = DockerCmd(self, 'kill', subargs, verbose=False)
            cmd = ("while [ -e %s/docker_kill_stress ]; "
                   "do %s || exit 255; done" % (self.tmpdir,
                                                docker_cmd.command))
            cmds.append(cmd)
        self.sub_stuff['kill_cmds'] = cmds

        signals.remove(19)  # SIGSTOP is also not catchable
        self.sub_stuff['signals_set'] = signals

        # SIGCONT after the test finishes (to resume possibly stopped container
        self.sub_stuff['cont_docker'] = DockerCmd(self, 'kill',
                                                  ['-s 18'] + extra_subargs,
                                                  verbose=False)

        # kill -9
        self.sub_stuff['kill_docker'] = DockerCmd(self, 'kill', extra_subargs,
                                                  verbose=False)

    def _execute_stress_loops(self, kill_jobs):
        """
        Enables stress loops
        """
        self.sub_stuff['touch_result'] = utils.run("touch %s/docker_kill_"
                                                   "stress" % self.tmpdir)
        # Execute stress loops
        for cmd in self.sub_stuff['kill_cmds']:
            job = utils.AsyncJob(cmd, verbose=True)
            kill_jobs.append(job)

    def _wait_for_test_end(self, kill_jobs):
        """
        Waits test_length while checking for failures
        """
        endtime = time.time() + self.config['test_length']
        while endtime > time.time():
            for job in kill_jobs:
                if job.sp.poll() is not None:   # process finished
                    for job in kill_jobs:
                        self.logerror("cmd %s (%s)", job.command,
                                      job.sp.poll())
                    out = utils.run("ls %s/docker_kill_stress" % self.tmpdir,
                                    ignore_status=True).exit_status
                    self.logerror("ls %s/docker_kill_stress (%s)", self.tmpdir,
                                  out)
                    raise xceptions.DockerTestFail("stress command finished "
                                                   "unexpectedly, see log for "
                                                   "details.")

    def _stop_stressers(self, kill_jobs):
        """
        Stops the stressers
        """
        cmd = "rm -f %s/docker_kill_stress" % self.tmpdir
        self.sub_stuff['rm_result'] = utils.run(cmd)

        self.sub_stuff['kill_results'] = []
        for job in kill_jobs:
            try:
                self.sub_stuff['kill_results'].append(job.wait_for(5))
            # job can raise whatever exception it wants, disable W0703
            except Exception, details:  # pylint: disable=W0703
                self.logerror("Job %s did not finish: %s", job.command,
                              str(details))
        del self.sub_stuff['kill_jobs']

    def _check_the_output(self, container_cmd):
        """
        Checks the output
        """
        signals_set = self.sub_stuff['signals_set']
        _check = self.config['check_stdout']
        cmd = self.sub_stuff['cont_docker']
        self.sub_stuff['kill_results'].append(cmd.execute())
        endtime = time.time() + self.config['stress_cmd_timeout']
        line = None
        out = None
        while endtime > time.time():
            try:
                out = container_cmd.stdout.splitlines()
                for line in [_check % sig for sig in signals_set]:
                    # out is always list in this branch, disable false E1103
                    out.remove(line)    # pylint: disable=E1103
                break
            except ValueError:
                pass
        else:
            self.fail_missing(_check, signals_set, Output(container_cmd, 0),
                              line)

    def _destroy_container(self, container_cmd):
        """
        Stops the container with kill -9 signal
        """
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

    def run_once(self):
        kill_base.run_once(self)
        container_cmd = self.sub_stuff['container_cmd']
        kill_jobs = self.sub_stuff['kill_jobs'] = []

        self._execute_stress_loops(kill_jobs)
        self._wait_for_test_end(kill_jobs)
        self._stop_stressers(kill_jobs)
        self._check_the_output(container_cmd)
        self._destroy_container(container_cmd)

    def pre_cleanup(self):
        if not self.sub_stuff.get('rm_result'):
            utils.run("rm -f %s/docker_kill_stress" % self.tmpdir,
                      ignore_status=True)
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


class parallel_stress_ttyoff(parallel_stress):

    """ non-tty version of the parallel_stress test """
    tty = False


class run_sigproxy_stress_parallel(parallel_stress):

    """ sigproxy version of the parallel_stress test """


class run_sigproxy_stress_parallel_ttyoff(parallel_stress):

    """ non-tty sigproxy version of the parallel_stress test """
    tty = False
