"""
Summary
-------
Checks that docker daemon is running with expected command-line options.

Operational Summary
-------------------
Get the full command line of the currently-running docker or docker-latest
daemon. Check for presence of expected option flags.

"""

import dockertest.docker_daemon
from dockertest import subtest
from dockertest.xceptions import DockerTestNAError


class run_flags(subtest.SubSubtestCaller):
    pass


class run_flags_deferred_removal(subtest.SubSubtest):
    """
    deferred removal option should always be set when running
    with devicemapper.
    """

    def postprocess(self):
        super(run_flags_deferred_removal, self).postprocess()
        docker_cmdline = ' '.join(dockertest.docker_daemon.cmdline())

        # deferred removal only meaningful with devicemapper
        self.failif_not_in(' --storage-driver devicemapper',
                           docker_cmdline,
                           "docker command-line options",
                           DockerTestNAError)

        self.failif_not_in(' --storage-opt dm.use_deferred_removal=true',
                           docker_cmdline,
                           "docker command-line options")
