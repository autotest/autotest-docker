r"""
Summary
----------

This test checks different ``docker run -a xxx`` variants.

Operational Summary
----------------------

#. Starts `docker run` with defined combination of `-a ...`
   each subtest executes 6 variants of tty/non-tty vs stdin/out/err.
#. Analyze results (exit_code, input_handling, correct_output)
"""
import re
from autotest.client import utils
from dockertest import config, xceptions, subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage


# LS_BAD is split into three elements. That's deliberate: coreutils 8.25ish
# changes error messages such that file paths are in quotes. The 3-part form
# below works with RHEL7 and F26 versions of coreutils, quotes or not.
LS_GOOD = ["bin", "etc", "lib", "root", "var"]
LS_BAD = ["cannot access", "/I/hope/this/does/not/exist/",
          ": No such file or directory"]


class run_attach(subtest.SubSubtestCaller):

    """ Subtest caller """

    pass


class run_attach_base(subtest.SubSubtest):

    """ Base class """

    # FIXME: Use stdin=None when BZ1113085 is resolved
    # FIXME: Review the results when BZ1131592 is resolved

    def _init_container(self, tty, cmd, cmd_input='\n'):
        """
        Starts container
        """
        name = self.sub_stuff['dc'].get_unique_name()
        self.sub_stuff['containers'].append(name)
        subargs = self.sub_stuff['subargs'][:]
        if tty:
            subargs.append('--tty=true')
        else:
            subargs.append('--tty=false')
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append(cmd)
        cmd = DockerCmd(self, 'run', subargs, timeout=30)
        try:
            cmd.execute(cmd_input)
        finally:
            result = cmd.cmdresult
        return result

    def _init_test_dependent(self):
        """
        Override this with your desired test setup.
        """
        raise NotImplementedError("Override this method in your test!")

    def _populate_expected_results(self):
        """
        Fills expected results based on self.sub_stuff['subargs']
        """
        def tty_booth(key, value):
            """ Fill tty=True and tty=False variants with the same value """
            self.sub_stuff['%s_True' % key] = value
            self.sub_stuff['%s_False' % key] = value

        is_stdin = '-a stdin' in self.sub_stuff['subargs']
        is_stdout = '-a stdout' in self.sub_stuff['subargs']
        is_stderr = '-a stderr' in self.sub_stuff['subargs']
        self.logdebug("Testing with arguments: stdin=%s, stdout=%s, stderr=%s",
                      is_stdin, is_stdout, is_stderr)
        if not is_stdin and not is_stdout and not is_stderr:
            # default behaves as '-a stdout -a stderr'
            is_stdout = True
            is_stderr = True
        elif is_stdin and not is_stdout and not is_stderr:
            # No otput only detached container should be started.
            tty_booth('exp_stdin', [r'[0-9a-fA-F]{64}'])
            tty_booth('exp_stdout', [r'[0-9a-fA-F]{64}'])
            tty_booth('exp_stderr', [r'[0-9a-fA-F]{64}'])
            tty_booth('exp_stdin_exit', 0)
            tty_booth('exp_stdout_exit', 0)
            tty_booth('exp_stderr_exit', 0)
            return
        tty_booth('exp_stdout_exit', 0)     # good ls returns exit 0
        tty_booth('exp_stderr_exit', 2)     # bad ls returns exit 2
        if is_stdin:   # process terminates using stdin
            tty_booth('exp_stdin_exit', 0)
        else:       # process never terminates (stdin is not used)
            tty_booth('exp_stdin_exit', 0)
            tty_booth('exp_stdin_not', LS_GOOD)     # ls command not executed
            tty_booth('exp_stdin_err_not', LS_GOOD)
        if is_stdout:
            if is_stdin:   # ls command executed and is present
                tty_booth('exp_stdin', LS_GOOD)
            if is_stdout:
                self.sub_stuff['exp_stderr_True'] = LS_BAD
            else:
                self.sub_stuff['exp_stderr_not_True'] = LS_BAD
                self.sub_stuff['exp_stderr_err_not_True'] = LS_BAD
            tty_booth('exp_stdout', LS_GOOD)
        else:
            tty_booth('exp_stdout_not', LS_GOOD)
            tty_booth('exp_stdout_err_not', LS_GOOD)
        if is_stderr:
            self.sub_stuff['exp_stderr_err_not_True'] = LS_BAD
            self.sub_stuff['exp_stderr_err_False'] = LS_BAD
        else:
            self.sub_stuff['exp_stderr_not_False'] = LS_BAD
            self.sub_stuff['exp_stderr_err_not_False'] = LS_BAD
            tty_booth('exp_stderr_err_not', LS_BAD)

    def initialize(self):
        """
        Execute 6 variants of the same 'docker run -a' command and store
        the results.
        variants:
          - tty
          - nontty
        variants:
          - stdin (execute bash, put 'ls /\n exit\n' on stdin)
          - stdout (execute ls /)
          - stderr (execute ls /nonexisting/directory/...)
        """
        super(run_attach_base, self).initialize()
        # Prepare a container
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['containers'] = []
        self._init_test_dependent()
        # TODO: Test w/ tty=True when some DockerCmd class supports pty
        # for tty in (True, False):   # generate matrix of tested variants
        tty = False
        # interactive container
        cont = self._init_container(tty, 'bash', 'ls /\nexit\n')
        self.sub_stuff['res_stdin_%s' % tty] = cont
        # stdout container
        cont = self._init_container(tty, 'ls /')
        self.sub_stuff['res_stdout_%s' % tty] = cont
        # stderr container
        cont = self._init_container(tty,
                                    'ls /I/hope/this/does/not/exist/%s'
                                    % utils.generate_random_string(6))
        self.sub_stuff['res_stderr_%s' % tty] = cont

    def _check_result(self, test, tty):
        def check_output(exps, notexps, act1, act2, result):
            """
            1. Checks if exps strings are in act1 output and not in act2
            2. Checks if notexps strings are not in act1 (doesn't care of act2)
            """
            act_name = act1
            act1 = getattr(result, act1)
            act2 = getattr(result, act2)
            for exp in exps:
                if not re.findall(exp, act1):
                    self.logerror("%sExpr '%s' not in %s:\n%s", prefix, exp,
                                  act_name, result)
                    return 1
                elif re.findall(exp, act2):
                    self.logerror("%sExpr '%s' was expected in %s and is also"
                                  "in the other out:\n%s", prefix, exp,
                                  act_name, result)
                    return 1
            for notexp in notexps:
                if re.findall(notexp, act1):
                    self.logerror("%sString '%s' present in %s:\n%s", prefix,
                                  notexp, act_name, result)
                    return 1
            return 0
        # check exit status
        prefix = 'test %s, tty %s: ' % (test, tty)
        exp = self.sub_stuff['exp_%s_exit_%s' % (test, tty)]
        try:
            dkrcmd = self.sub_stuff['res_%s_%s' % (test, tty)]
            act = dkrcmd.exit_status
        except AttributeError:
            raise xceptions.DockerTestError("Command was not executed: %s"
                                            % dkrcmd)
        if exp != act:
            self.logerror("%sExit status of:\n%s\nis not %s", prefix,
                          self.sub_stuff['res_%s_%s' % (test, tty)], exp)
            return 1
        # check stdout
        if check_output(self.sub_stuff.get('exp_%s_%s' % (test, tty), []),
                        self.sub_stuff.get('exp_%s_not_%s' % (test, tty), []),
                        'stdout', 'stderr',
                        self.sub_stuff['res_%s_%s' % (test, tty)]):
            return 1
        # check stderr
        if check_output(self.sub_stuff.get('exp_%s_err_%s' % (test, tty), []),
                        self.sub_stuff.get('exp_%s_err_not_%s' % (test, tty),
                                           []),
                        'stderr', 'stdout',
                        self.sub_stuff['res_%s_%s' % (test, tty)]):
            return 1
        return 0

    def postprocess(self):
        super(run_attach_base, self).postprocess()
        failures = 0
        # TODO: Test w/ tty=True when some DockerCmd class supports pty
        # for tty in (True, False):   # generate matrix of tested variants
        tty = False
        failures += self._check_result('stdin', tty)
        failures += self._check_result('stdout', tty)
        failures += self._check_result('stderr', tty)
        self.failif(failures, "%s of subtest variants failed, please check "
                    "the log for details." % failures)

    def cleanup(self):
        super(run_attach_base, self).cleanup()
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            dc.clean_all(self.sub_stuff.get("containers"))


class none(run_attach_base):

    """
    By default stdout and stderr is attached. Stdin is not so stdin test
    should fail.
    """

    def _init_test_dependent(self):
        self.sub_stuff['subargs'] = ['']
        self._populate_expected_results()


class stdin(run_attach_base):

    """
    Currently when no output is attached, container is started as detached
    (prints the container's id)
    """

    def _init_test_dependent(self):
        self.sub_stuff['subargs'] = ['-a stdin']
        self._populate_expected_results()


class stdout(run_attach_base):

    """
    Only stdout is attached, stdin fails and no output in stderr.
    """

    def _init_test_dependent(self):
        self.sub_stuff['subargs'] = ['-a stdout']
        self._populate_expected_results()


class stderr(run_attach_base):

    """
    Only stderr is attached, stdin fails, no output in stdout.
    """

    def _init_test_dependent(self):
        self.sub_stuff['subargs'] = ['-a stderr']
        self._populate_expected_results()


class in_out(run_attach_base):

    """
    stdin/stdout are attached, no output in stderr
    """

    def _init_test_dependent(self):
        self.sub_stuff['subargs'] = ['-a stdin', '-a stdout']
        self._populate_expected_results()


class in_err(run_attach_base):

    """
    stdin/stderr are attached, no output in stdout
    """

    def _init_test_dependent(self):
        self.sub_stuff['subargs'] = ['-a stdin', '-a stderr']
        self._populate_expected_results()


class in_out_err(run_attach_base):

    """
    All streams attached, output should be found in correct streams.
    """

    def _init_test_dependent(self):
        self.sub_stuff['subargs'] = ['-a stdin', '-a stdout', '-a stderr']
        self._populate_expected_results()


class i_stdin(stdin):

    """
    Currently when no output is attached, container is started as detached
    (prints the container's id)
    :note: uses --interactive
    """

    def _init_test_dependent(self):
        super(i_stdin, self)._init_test_dependent()
        self.sub_stuff['subargs'].append('--interactive')


class i_in_out(in_out):

    """
    stdin/stdout are attached, no output in stderr
    :note: uses --interactive
    """

    def _init_test_dependent(self):
        super(i_in_out, self)._init_test_dependent()
        self.sub_stuff['subargs'].append('--interactive')


class i_in_err(in_err):

    """
    stdin/stderr are attached, no output in stdout
    :note: uses --interactive
    """

    def _init_test_dependent(self):
        super(i_in_err, self)._init_test_dependent()
        self.sub_stuff['subargs'].append('--interactive')


class i_in_out_err(in_out_err):

    """
    All streams attached, output should be found in correct streams.
    :note: uses --interactive
    """

    def _init_test_dependent(self):
        super(i_in_out_err, self)._init_test_dependent()
        self.sub_stuff['subargs'].append('--interactive')
