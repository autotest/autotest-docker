r"""
Summary
-------

Preserve docker versions in state files.

Operational Summary
-------------------

#. Run 'docker version'; use DockerVersion module to parse output
#. Run 'rpm -q docker|docker-latest' (whichever one is in use)
#. Preserve output in sysinfo files

"""

import os.path
from autotest.client import utils
from dockertest import subtest
from dockertest.dockercmd import DockerCmd
from dockertest.output import DockerVersion, mustpass
from dockertest.docker_daemon import which_docker


class log_versions(subtest.Subtest):

    def run_once(self):
        """
        Determine the installed version of docker, and preserve it
        in a sysinfo file.
        """
        super(log_versions, self).run_once()
        cmdresult = mustpass(DockerCmd(self, "version").execute())
        docker_version = DockerVersion(cmdresult.stdout)
        info = ("docker version client: %s server %s"
                % (docker_version.client, docker_version.server))
        self.loginfo("Found %s", info)
        self.write_sysinfo('docker_version', info + "\n")
        self.write_sysinfo('docker_rpm_active', self._rpmq(which_docker()))
        self.write_sysinfo('docker_rpm_current', self._rpmq('docker'))
        self.write_sysinfo('docker_rpm_latest', self._rpmq('docker-latest'))

    def write_sysinfo(self, filename, content):
        """
        Write the given content to sysinfodir/filename
        """
        path = os.path.join(self.job.sysinfo.sysinfodir, filename)
        with open(path, 'wb') as outfile:
            outfile.write(content)

    @staticmethod
    def _rpmq(package_name):
        return utils.run("rpm -q %s" % package_name).stdout
