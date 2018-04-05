r"""
Summary
---------

Test live-restore: running container should survive docker daemon restart.

Operational Summary
----------------------

#. Run a docker container
#. Restart docker daemon
#. Verify that container is listed under 'docker ps' and is still running.

Operational Detail
------------------

Our test container outputs a string (it doesn't matter what) every
second. We check that it's running by running `docker logs` repeatedly
until we get a new line; timing out at five seconds.

We *restart* the docker daemon, not separate stop and then start.
(The latter would give us more testing options, such as confirming
continued output from the container, but there's also a lot more
possibility of leaving our system in an undefined state if something
goes wrong between stop and start.) We then check that docker still
lists the container in 'docker ps' and that the container is still
emitting output lines.

Prerequisites
-------------

This test is only applicable if docker daemon is run with --live-restore
option; we abort with TestNAError if it isn't.

live-restore also requires `KillMode=process` in the systemd unit file of
the controlling process - typically dockerd but possibly docker-containerd.
Without that key, the container is stopped on daemon restart; see
rhbz1424709#c40 and rhbz1460266.

"""

import time
from autotest.client import utils
import dockertest.docker_daemon as docker_daemon
from dockertest import subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest.images import DockerImage
from dockertest.output import DockerInfo
from dockertest.output.validate import mustpass
from dockertest.xceptions import DockerTestNAError


class liverestore(subtest.Subtest):

    def initialize(self):
        super(liverestore, self).initialize()

        # Skip test if live-restore is not enabled
        try:
            lr_enabled = DockerInfo().get('Live Restore Enabled')
            self.failif_ne(lr_enabled, 'true',
                           "Live Restore Enabled field from 'docker info'",
                           DockerTestNAError)
        except KeyError:
            # docker 1.12 doesn't include this in 'docker info'. Try looking
            # at command line. This won't work with containerized docker
            # because it uses /etc/docker/*.json
            docker_cmdline = docker_daemon.cmdline()
            self.failif_not_in("--live-restore", docker_cmdline,
                               "docker daemon command-line options",
                               DockerTestNAError)

        # rhbz1424709#c40 : live-restore fails unless KillMode=process
        killmode = docker_daemon.systemd_show('KillMode')
        if killmode != 'process':
            self.logwarning("systemd KillMode is '%s' (expected 'process')."
                            " See rhbz1424709." % killmode)

        self.stuff['dc'] = DockerContainers(self)

    def run_once(self):
        super(liverestore, self).run_once()

        self._start_container()
        self._verify_that_container_is_running()

        # Restart docker daemon. It should be nearly instantaneous; if it
        # takes ~90 seconds it could be another symptom of rhbz1424709.
        # The warning message might help someone diagnose a later failure.
        # 2018-04-04 also restart docker-containerd. This is currently
        # only meaningful for Fedora 28; the service doesn't exist on RHEL.
        # So don't actually check exit status.
        self.stuff['dockerd_pid_orig'] = docker_daemon.pid()
        self.stuff['container_pid_orig'] = self._container_pid()
        t0 = time.time()
        utils.run('systemctl restart docker-containerd.service',
                  ignore_status=True)
        docker_daemon.restart()
        t1 = time.time()
        if t1 - t0 > 30:
            self.logwarning("docker restart took %d seconds", t1 - t0)

        # Wait until docker is back
        def _docker_is_active():
            result = docker_daemon.systemd_action('is-active').stdout.strip()
            self.logdebug("is-active -> %s" % result)
            return result == 'active'

        self.failif(utils.wait_for(_docker_is_active, 15, step=1) is None,
                    "Timed out waiting for docker daemon ")

    def _start_container(self):
        """
        Start a container. All it does is emit output to stdout, one
        line per second. We don't care what the output is, we just
        care that the number of output lines increases over time.
        """
        c_name = self.stuff['dc'].get_unique_name()

        fin = DockerImage.full_name_from_defaults(self.config)
        subargs = ['--detach', '--name=' + c_name, fin,
                   'bash -c "echo READY;'
                   ' while :; do date +%s; sleep 1;done"']
        dkrcmd = AsyncDockerCmd(self, 'run', subargs)
        dkrcmd.execute()
        dkrcmd.wait_for_ready(c_name)
        self.stuff['container_name'] = c_name

    def _verify_that_container_is_running(self):
        """
        Verify that container process is running, by running 'docker log'
        on it sequentially and making sure that we get new output lines.
        """
        log_0 = self._container_log()

        # Wait up to 5 seconds for output to change
        end_at = time.time() + 5
        while time.time() <= end_at:
            log_1 = self._container_log()
            if log_1 != log_0:
                break
            time.sleep(1)

        self.failif(len(log_0) == len(log_1),
                    "Container log line count did not grow")

    def _container_log(self):
        """
        Returns container log as a list of strings
        """
        c_name = self.stuff['container_name']
        result = mustpass(DockerCmd(self, "logs", [c_name]).execute())
        return result.stdout.strip().split("\n")

    def _container_pid(self):
        dc = self.stuff['dc']
        inspect = dc.json_by_name(self.stuff['container_name'])
        return int(inspect[0]['State']['Pid'])

    def postprocess(self):
        super(liverestore, self).postprocess()

        # Run 'docker ps', confirm that container is listed and is active
        dc = self.stuff['dc']
        docker_ps = dc.list_containers_with_name(self.stuff['container_name'])
        self.failif(not docker_ps,
                    "Container not in 'docker ps' output after restart")
        self.failif_not_in("Up ", docker_ps[0].status,
                           "container status as reported by 'docker ps'")

        # Confirm that container is still running (spitting out lines)
        self._verify_that_container_is_running()

        # Confirm that docker daemon PID has changed
        self.failif(self.stuff['dockerd_pid_orig'] == docker_daemon.pid(),
                    "docker daemon PID did not change after restart")

        # ...and the container PID hasn't
        self.failif_ne(self._container_pid(),
                       self.stuff['container_pid_orig'],
                       "Container PID changed after dockerd restart")

    def cleanup(self):
        super(liverestore, self).cleanup()
        if self.config['remove_after_test']:
            if 'container_name' in self.stuff:
                self.stuff['dc'].clean_all([self.stuff['container_name']])
