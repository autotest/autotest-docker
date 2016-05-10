from run import run_base
from dockertest.output import DockerVersion


class run_tmpfs(run_base):
    #: Run container with --tmpfs option and verifies that it is mounted

    def initialize(self):
        super(run_tmpfs, self).initialize()
        # Minimum docker version 1.10 is required for --tmpfs
        DockerVersion().require_server("1.10")

    def run_once(self):
        super(run_tmpfs, self).run_once()
        try:
            self.sub_stuff["cont"].wait_by_name(self.sub_stuff['name'])
        except ValueError:
            pass  # container already finished and exited

    def postprocess(self):
        super(run_tmpfs, self).postprocess()
        actual_exit_status = self.sub_stuff['dkrcmd'].exit_status
        expected_exit_status = self.config['exit_status']
        cmd = self.sub_stuff['dkrcmd'].command
        self.failif_ne(actual_exit_status, expected_exit_status,
                       "exit status from %s" % cmd)
        tmpfs_mnt = self.config['tmpfs_path']
        tmpfs_mnted = self.sub_stuff['dkrcmd'].stdout.find(tmpfs_mnt) != -1
        self.failif(not tmpfs_mnted,
                    "Given --tmpfs not mounted: --tmpfs %s" % tmpfs_mnt)
