"""
Test autorestart of docker container after docker daemon restart.

#. Stop system docker daemon
#. Start test docker daemon with special work dir (graph) path.
#. Start infinite docker container which react to SIGTERM.
#. Restart docker daemon.
#. Check if docker container is auto restarted after docker restart.

Test fails because process with PID 1 in docker native execute driver don't get
any signal which is not set to be listened is not send to process at all,
only exceptions are SIGKILL or SIGSTOP. This special behavior comes from linux
PID namespaces.
"""
# pylint: disable=E0611
from restart import restart_container_autorestart_base


class restart_container_autorestart(restart_container_autorestart_base):

    def postprocess(self):
        super(restart_container_autorestart, self).postprocess()

        i = self.conts.get_container_metadata(self.sub_stuff["cont1_name"])
        self.failif(i is None,
                    "Container was probably not created.")

        daemon_stdout = ""
        daemon_stderr = ""
        if "docker_daemon" in self.sub_stuff:
            daemon_stdout = self.sub_stuff["docker_daemon"].get_stdout()
            daemon_stderr = self.sub_stuff["docker_daemon"].get_stderr()

        if not i[0]["State"]["Running"]:
            self.logdebug("\nDAEMON-STDOUT:\n"
                          "%s\nDAEMON-STDERR:\n%s" % (daemon_stdout,
                                                      daemon_stderr))

        self.failif(not i[0]["State"]["Running"],
                    "Container was not autorestarted after docker "
                    "daemon restart. Closer detail in debug.")
