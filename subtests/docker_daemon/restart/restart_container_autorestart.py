"""
Test autorestart of docker container after docker daemon restart.

1. Stop system docker daemon
2. Start test docker daemon with special work dir (graph) path.
3. Start infinite docker container.
4. Restart docker daemon.
5. Check if docker container is auto restarted after docker restart.

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

        self.failif(not i[0]["State"]["Running"],
                    "Container was not autorestarted after docker "
                    "daemon restart.")
