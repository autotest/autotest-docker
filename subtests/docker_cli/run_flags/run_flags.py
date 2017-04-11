"""
Summary
-------
Checks that docker daemon is running with expected command-line options.

Operational Summary
-------------------
Get the full command line of the currently-running docker or docker-latest
daemon. Check for presence of expected option flags.

"""

import os
from distutils.version import LooseVersion   # pylint: disable=E0611,F0401
import dockertest.docker_daemon
from dockertest import subtest
from dockertest.output import DockerVersion
from dockertest.xceptions import DockerTestFail, DockerTestNAError


class run_flags(subtest.SubSubtestCaller):
    pass


class run_flags_base(subtest.SubSubtest):

    def has_storage_opt(self, wanted):
        docker_cmdline = dockertest.docker_daemon.cmdline()
        self.logdebug("docker daemon command line: %s", docker_cmdline)
        last_opt = ''
        for opt in docker_cmdline:
            if opt == wanted and last_opt == '--storage-opt':
                return True
            last_opt = opt
        self.logwarning("Option '%s' not in %s" % (wanted, docker_cmdline))
        return False


class run_flags_deferred_removal(run_flags_base):
    """
    deferred REMOVAL should always be set in all docker versions we test.
    """

    def postprocess(self):
        super(run_flags_deferred_removal, self).postprocess()
        if self.has_storage_opt('dm.use_deferred_removal=true'):
            return
        raise DockerTestFail("missing option: dm.use_deferred_removal")


class run_flags_deferred_deletion(run_flags_base):
    """
    deferred DELETION should be set in docker >= 1.12 but only if
    the kernel supports it.
    """

    def postprocess(self):
        super(run_flags_deferred_deletion, self).postprocess()

        # Check flag first. It's quick, and if it passes, we're good.
        if self.has_storage_opt('dm.use_deferred_deletion=true'):
            return

        # Flag missing. This is OK under some circumstances.
        DockerVersion().require_server("1.12")
        self._check_kernel_support()

        raise DockerTestFail("missing option: dm.use_deferred_deletion")

    @staticmethod
    def _check_kernel_support():
        """
        Fail with N/A if kernel doesn't support deferred deletion.
        """
        required = LooseVersion("3.10.0-632")    # in RHEL 7.4
        actual = LooseVersion(os.uname()[2])
        if actual < required:
            raise DockerTestNAError("Deferred deletion functionality"
                                    " requires kernel >= %s; this is %s"
                                    % (required, actual))
