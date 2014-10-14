"""
Test stop of docker daemon and check if there left some "mess" after that.
"mess" open files, unmounted directories, etc..

#. Stop system docker daemon
#. Start test docker daemon with special work dir (graph) path.
#. Start docker container.
#. Wait until docker container is finished.
#. Stop test docker daemon.
#. Check if no folder in docker work dir is mounted.
#. Try to delete docker work dir.
"""
# pylint: disable=E0611
import os
from autotest.client.shared import utils
from restart import restart_check_mess_after_stop_base


class restart_check_mess_after_stop(restart_check_mess_after_stop_base):

    def postprocess(self):
        super(restart_check_mess_after_stop, self).postprocess()

        g_path = self.sub_stuff["graph_path"]
        wait = lambda: g_path not in self.list_mounted_dirs().stdout
        utils.wait_for(wait, 60)

        res = self.list_mounted_dirs()
        self.failif(res.exit_status != 0,
                    "Mount command was not successful\n%s" % res)

        self.failif(g_path in res.stdout,
                    "All folders mounted by docker should be after docker"
                    "finish unmounted.:\n%s" % res.stdout)

        self.failif(not os.path.exists(self.sub_stuff["graph_path"]),
                    "Docker working directory (graph) not exists: %s" %
                    os.path.exists(self.sub_stuff["graph_path"]))

        res = self.rm_graph_dir()
        self.failif(res.exit_status != 0,
                    "rm command was not successful\n%s" % res)
        self.sub_stuff["containers"].remove(self.sub_stuff["cont1_name"])

    @staticmethod
    def list_mounted_dirs():
        return utils.run("mount")

    def rm_graph_dir(self):
        return utils.run("rm -rf %s" % self.sub_stuff["graph_path"], 60)
