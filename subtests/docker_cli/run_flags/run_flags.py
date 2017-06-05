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
from dockertest.xceptions import DockerTestFail


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
