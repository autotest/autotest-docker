r"""
Summary
----------

This test checks correctness of docker run -u ...

Operational Summary
--------------------

1.  get container's /etc/passwd
2.  generate uid which suits the test needs (nonexisting, existing name, uid..)
3.  execute docker run -u ... echo $UID:$GID; whoami
4.  check results (pass/fail/details)
"""
from autotest.client import utils
from dockertest import config, xceptions, subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.output import OutputGood


class run_user(subtest.SubSubtestCaller):

    """ Subtest caller """

    def _get_passwd_from_container(self):
        """
        Get /etc/passwd from container (it's used to generate correct uids)
        """
        name = self.stuff['dc'].get_unique_name("initialization", length=4)
        self.stuff['container'] = name
        subargs = ['--rm', '--interactive']
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append("cat /etc/passwd")
        cmd = DockerCmd(self, 'run', subargs)
        result = cmd.execute()
        self.failif_ne(result.exit_status, 0,
                       "Failed to get container's /etc/passwd."
                       " Exit status is !0\n%s" % result)
        OutputGood(result)
        return result.stdout

    def initialize(self):
        super(run_user, self).initialize()
        self.stuff['dc'] = DockerContainers(self)
        self.stuff['passwd'] = self._get_passwd_from_container()

    def cleanup(self):
        """
        Cleanup the container
        """
        super(run_user, self).cleanup()
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            dc.clean_all([self.stuff.get("container")])


class run_user_base(subtest.SubSubtest):

    """ Base class """

    def _init_container(self, subargs, cmd):
        """
        Starts container
        """
        name = self.sub_stuff['dc'].get_unique_name()
        self.sub_stuff['container'] = name
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append("bash")
        subargs.append("-c")
        subargs.append(cmd)
        self.sub_stuff['cmd'] = DockerCmd(self, 'run', subargs)

    def _init_test_dependent(self):
        """
        Override this with your desired test setup.
        """
        self.sub_stuff['execution_failure'] = None
        self.sub_stuff['uid_check'] = None
        self.sub_stuff['whoami_check'] = None
        self.sub_stuff['subargs'] = None
        raise NotImplementedError("Override this method in your test!")

    def initialize(self):
        """
        Runs one container
        """
        super(run_user_base, self).initialize()
        # Prepare a container
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self)
        self._init_test_dependent()
        self._init_container(self.sub_stuff['subargs'],
                             self.config['exec_cmd'])

    def run_once(self):
        """
        Execute docker and store the results
        """
        super(run_user_base, self).run_once()
        self.sub_stuff['result'] = self.sub_stuff['cmd'].execute()

    def postprocess(self):
        super(run_user_base, self).postprocess()
        # Exit status
        if self.sub_stuff['execution_failure']:
            self._postprocess_bad()
        else:
            self._postprocess_good()

    def _postprocess_bad(self):
        """
        Check that container execution failed with correct message
        """
        result = self.sub_stuff['result']
        self.failif(result.exit_status == 0, "Container's exit status is "
                    "0, although it should failed:\n0%s"
                    % result)
        output = (str(result.stdout) + str(result.stderr))
        self.failif((self.sub_stuff['execution_failure']
                     not in output),
                    "Expected failure message '%s' is not in the "
                    "container's output:\n%s"
                    % (self.sub_stuff['execution_failure'], output))

    def _postprocess_good(self):
        """
        Check that container executed correctly and that output is as expected
        """
        result = self.sub_stuff['result']
        OutputGood(result)
        self.failif_ne(result.exit_status, 0,
                       "Container's exit status is !0 although it should pass"
                       ":\n%s" % result)
        output = (str(result.stdout) + str(result.stderr))
        self.failif(self.sub_stuff['uid_check'] not in output, "UID "
                    "check line '%s' not present in the container output:\n%s"
                    % (self.sub_stuff['uid_check'], result))
        self.failif(self.sub_stuff['whoami_check'] not in output,
                    "whoami check line '%s' not present in the container "
                    "output:\n%s" % (self.sub_stuff['whoami_check'], result))

    def cleanup(self):
        """
        Cleanup the container
        """
        super(run_user_base, self).cleanup()
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            dc.clean_all([self.sub_stuff.get("container")])


class default(run_user_base):

    """
    Doesn't use "-u" and expects the default user to be root::0
    """

    def _init_test_dependent(self):
        self.sub_stuff['execution_failure'] = False
        self.sub_stuff['uid_check'] = "UIDCHECK: 0:"
        self.sub_stuff['whoami_check'] = "WHOAMICHECK: root"
        self.sub_stuff['subargs'] = ['--rm', '--interactive']


class named_user(run_user_base):

    """
    Finds any user but root existing on container and uses it by name
    """

    def _init_test_dependent(self):
        user = None
        for line in self.parent_subtest.stuff['passwd'].splitlines():
            line = line.strip()
            if not line or line.startswith('root') or line.startswith('#'):
                continue
            user, _, uid, _ = line.split(':', 3)
            break
        if not user:
            msg = ("This container's image doesn't contain passwd with "
                   "multiple users, unable to execute this test\n%s"
                   % self.parent_subtest.stuff['passwd'])
            raise xceptions.DockerTestNAError(msg)
        self.sub_stuff['execution_failure'] = False
        self.sub_stuff['uid_check'] = "UIDCHECK: %s:" % uid
        self.sub_stuff['whoami_check'] = "WHOAMICHECK: %s" % user
        self.sub_stuff['subargs'] = ['--rm', '--interactive',
                                     '--user=%s' % user]


class num_user(run_user_base):

    """
    Finds any user but root existing on container and uses it by uid
    """

    def _init_test_dependent(self):
        user = None
        for line in self.parent_subtest.stuff['passwd'].splitlines():
            line = line.strip()
            if not line or line.startswith('root') or line.startswith('#'):
                continue
            user, _, uid, _ = line.split(':', 3)
            break
        if not user:
            msg = ("This container's image doesn't contain passwd with "
                   "multiple users, unable to execute this test\n%s"
                   % self.parent_subtest.stuff['passwd'])
            raise xceptions.DockerTestNAError(msg)
        self.sub_stuff['execution_failure'] = False
        self.sub_stuff['uid_check'] = "UIDCHECK: %s:" % uid
        self.sub_stuff['whoami_check'] = "WHOAMICHECK: %s" % user
        self.sub_stuff['subargs'] = ['--rm', '--interactive',
                                     '--user=%s' % uid]


class bad_user(run_user_base):

    """
    Generates user name which doesn't exist in containers passwd
    """

    def _init_test_dependent(self):
        users = []
        for line in self.parent_subtest.stuff['passwd'].splitlines():
            line = line.strip()
            try:
                users.append(line.split(':', 1)[0])
            except IndexError:
                pass
        user = utils.get_unique_name(lambda name: name not in users, "user",
                                     length=6)
        self.sub_stuff['execution_failure'] = "Unable to find user %s" % user
        self.sub_stuff['subargs'] = ['--rm', '--interactive',
                                     '--user=%s' % user]


class bad_number(run_user_base):

    """
    Generates user id which doesn't exist in containers passwd
    (it should start, print correct uid, but whoami should fail)
    """

    def _init_test_dependent(self):
        uid = False
        uids = []
        for line in self.parent_subtest.stuff['passwd'].splitlines():
            line = line.strip()
            try:
                uids.append(int(line.split(':', 3)[2]))
            except (IndexError, TypeError):
                pass
        for i in xrange(1, 2147483647):
            if i not in uids:
                uid = i
                break
        if uid is False:
            msg = ("This container's image passwd occupies all uids. Unable to"
                   " execute this test\n%s"
                   % self.parent_subtest.stuff['passwd'])
            raise xceptions.DockerTestNAError(msg)
        self.sub_stuff['execution_failure'] = False
        self.sub_stuff['uid_check'] = "UIDCHECK: %s:" % uid
        self.sub_stuff['whoami_check'] = ("whoami: cannot find name for user "
                                          "ID %s" % uid)
        self.sub_stuff['subargs'] = ['--rm', '--interactive',
                                     '--user=%s' % uid]


class too_high_number(run_user_base):

    """
    Uses incorrectly large uid number (2147483648)
    """

    def _init_test_dependent(self):
        self.sub_stuff['execution_failure'] = ("Uids and gids must be in "
                                               "range 0-2147483647")
        self.sub_stuff['subargs'] = ['--rm', '--interactive',
                                     '--user=2147483648']
