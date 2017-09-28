r"""
Summary
----------

Tests for bz1320302 - odd behavior of --cgroup-parent option.

Operational Summary
----------------------

#. Start container with --cgroup-parent=X, for various values of X
#. Run container command 'cat /proc/1/cgroup'
#. Confirm that each line (controller) lists the correct cgroup path
"""


import os
import os.path
import re
from autotest.client import utils
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.output import OutputGood, DockerVersion
from dockertest.subtest import SubSubtest, SubSubtestCaller
from dockertest.xceptions import DockerTestError, DockerTestFail


class run_cgroup_parent(SubSubtestCaller):
    pass


class run_cgroup_parent_base(SubSubtest):
    def _setup(self, cg_parent):
        """
        Set up test parameters: the value of the --cgroup--parent option.
        String may include {rand1} and/or {rand2}; we replace those with
        two pseudorandom strings.
        """
        DockerVersion().require_client("1.10")
        self.sub_stuff['rand1'] = utils.generate_random_string(8)
        self.sub_stuff['rand2'] = utils.generate_random_string(8)
        self.sub_stuff['cgroup_parent'] = cg_parent.format(**self.sub_stuff)

    def _expect(self, path=None, stderr=None, exit_status=0):
        """
        Set up test parameters: what to expect on completion.
        The format strings {rand1} and {rand2} will be replaced with the
        same values as in _setup, and the string {cid} with the container ID
        once we have it.
        """
        self.sub_stuff['expected_path'] = path if path else ''
        self.sub_stuff['expected_stderr'] = stderr if stderr else ''
        self.sub_stuff['expected_status'] = exit_status

    def run_once(self):
        """
        Run docker with the given --cgroup-parent; preserve cgroup info.
        """
        super(run_cgroup_parent_base, self).run_once()

        cidfile = os.path.join(self.tmpdir, 'cidfile')
        self.sub_stuff['cidfile'] = cidfile

        subargs = ['--rm',
                   '--cgroup-parent=%s' % self.sub_stuff['cgroup_parent'],
                   '--cidfile', cidfile,
                   DockerImage.full_name_from_defaults(self.config),
                   '/bin/cat', '/proc/1/cgroup']
        dc = DockerCmd(self, "run", subargs,
                       timeout=self.config['docker_timeout'])
        self.sub_stuff["cmdresult"] = dc.execute()

    def postprocess(self):
        super(run_cgroup_parent_base, self).postprocess()

        cmdresult = self.sub_stuff["cmdresult"]
        expected_status = self.sub_stuff["expected_status"]
        OutputGood(cmdresult, ignore_error=(expected_status != 0),
                   skip=['nonprintables_check'])

        self.sub_stuff["cid"] = self._read_cid()
        path_exp = self.sub_stuff['expected_path'].format(**self.sub_stuff)
        stderr_exp = self.sub_stuff['expected_stderr'].format(**self.sub_stuff)

        # Check stderr first: that way if we're not expecting an error, but
        # get one, our user has a better chance of seeing something useful.
        # (Note: Running docker with -D (debug) produces lots of cruft:
        #    time="...." level=debug msg="unwanted stuff"
        # Strip them out.)
        stderr = "\n".join([line
                            for line in cmdresult.stderr.strip().split("\n")
                            if not line.startswith('time="')])
        if stderr_exp:
            re_stderr = re.compile(stderr_exp)
            if not re.match(re_stderr, stderr):
                raise DockerTestFail("expected '%s' not found in stderr ('%s')"
                                     % (stderr_exp, stderr))
        else:
            self.failif_ne(stderr, stderr_exp, "unexpected stderr")

        # If we're expecting stdout, it must contain multiple lines each
        # of the form:
        #    <num>:<cgroup controller>:<path>
        # ...where <path> must exactly match the one in our test setup.
        stdout = cmdresult.stdout.strip()
        if path_exp:
            re_cgroup = re.compile(r'^(\d+):([^:]*):(.*)')
            found_match = False
            for line in stdout.split("\n"):
                m = re.match(re_cgroup, line)
                if m is None:
                    raise DockerTestFail("cgroup line does not conform to"
                                         " '<n>:<controller>:<path>': '%s'"
                                         % line)
                # bz1385924: 'pids' fails in docker-1.10; not worth fixing.
                if m.group(2) == 'pids':
                    if DockerVersion().server.startswith("1.10"):
                        continue
                self.failif_ne(m.group(3), path_exp, "cgroup path for %s:%s"
                               % (m.group(1), m.group(2)))
                found_match = True

            # Must find at least one matching cgroup line
            if not found_match:
                raise DockerTestFail("No output from cgroups")
        else:
            self.failif_ne(stdout, '', "unexpected output on stdout")

        # Check exit code last: the stdout/stderr diagnostics are more helpful
        self.failif_ne(cmdresult.exit_status, expected_status, "exit status")

    def _read_cid(self):
        """
        Read container ID from --cidfile file, so we can replace {cid}
        in format string and do an exact match on expected values.
        """
        try:
            cid = open(self.sub_stuff['cidfile'], 'rb').read().strip()
        except IOError:
            return "<n/a>"         # no cidfile, e.g. because of bad command
        if len(cid) < 12:
            raise DockerTestError("bad cid (length < 12) in --cidfile")
        return cid

    def cleanup(self):
        """
        Remove stray cgroups
        """
        super(run_cgroup_parent_base, self).cleanup()
        cgroups_dir = '/sys/fs/cgroup'
        try:
            rand1 = self.sub_stuff['rand1']
            rand2 = self.sub_stuff['rand2']
        except KeyError:                # Test never ran
            return

        for ent in os.listdir(cgroups_dir):
            # eg /sys/fs/cgroup/memory
            controller_dir = os.path.join(cgroups_dir, ent)
            if os.path.isdir(controller_dir):
                # eg /sys/fs/cgroup/memory/foo.slice
                rand1_dir = os.path.join(controller_dir, "%s.slice" % rand1)
                if os.path.isdir(rand1_dir):
                    # eg /sys/fs/cgroup/memory/foo.slice/foo-bar.slice
                    rand2_dir = os.path.join(rand1_dir,
                                             "%s-%s.slice" % (rand1, rand2))
                    # Note that this is special cgroupfs magic! rmdir
                    # succeeds even though ls lists "files" within.
                    if os.path.isdir(rand2_dir):
                        os.rmdir(rand2_dir)
                    os.rmdir(rand1_dir)


class run_cgroup_parent_invalid_name(run_cgroup_parent_base):
    """
    Invalid value for --cgroup-parent option
    """

    def initialize(self):
        super(run_cgroup_parent_invalid_name, self).initialize()
        self._setup("/{rand1}")
        self._expect(stderr=self.config['expect_stderr'], exit_status=125)


class run_cgroup_parent_path(run_cgroup_parent_base):
    """
    Perfectly valid slice. In docker < 1.9.1-25.el7 this produced
    weird results.
    """

    def initialize(self):
        super(run_cgroup_parent_path, self).initialize()
        self._setup("{rand1}.slice")
        self._expect(path="/{rand1}.slice/docker-{cid}.scope")


class run_cgroup_parent_path_with_hyphens(run_cgroup_parent_base):
    """
    Hyphens result in a more complicated path.
    """

    def initialize(self):
        super(run_cgroup_parent_path_with_hyphens, self).initialize()
        self._setup("{rand1}-{rand2}.slice")
        self._expect(path="/{rand1}.slice/{rand1}-{rand2}.slice"
                     "/docker-{cid}.scope")
