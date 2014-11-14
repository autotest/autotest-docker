"""
Summary
-------

This test uses the ``--ipc`` (System V shared memory segment) sharing feature
of the ``docker``. It creates segment and changes the value from multiple
places simultaneously on variuos setups.


Operational Summary
-------------------

1. Execute multiple workers from host and container according to setup
2. Wait until they finish/fail and analyze the output
3. Cleanup


Prerequisites
-------------

Host and containers have to have ``libc`` and ``librt`` libraries installed
or you might drop those libraries in $SRCDIR/src/{libc.so.x86_64,libc.so.i686,
librt.so.x86_64, ./librt.so.i686} and they'll get shared between host/guest.

"""
import os
import random
import shutil
import time

from autotest.client.shared import utils
from dockertest import subtest, xceptions, config
from dockertest.containers import DockerContainers
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest.images import DockerImage
from dockertest.output import OutputGood


class InteractiveAsyncDockerCmd(AsyncDockerCmd):

    """
    Execute docker command as asynchronous background process on ``execute()``
    with PIPE as stdin and allows use of stdin(data) to interact with process.
    """

    def __init__(self, subbase, subcmd, subargs=None, timeout=None,
                 verbose=True):
        super(InteractiveAsyncDockerCmd, self).__init__(subbase, subcmd,
                                                        subargs, timeout,
                                                        verbose)
        self._stdin = None
        self._stdout_idx = 0

    def execute(self, stdin=None):
        """
        Start execution of asynchronous docker command
        """
        ps_stdin, self._stdin = os.pipe()
        ret = super(InteractiveAsyncDockerCmd, self).execute(ps_stdin)
        os.close(ps_stdin)
        if stdin:
            for line in stdin.splitlines(True):
                self.stdin(line)
        return ret

    def stdin(self, data):
        """
        Sends data to stdin (partial send is possible!)
        :param data: Data to be send
        :return: Number of written data
        """
        return os.write(self._stdin, data)

    def close(self):
        """
        Close the pipes (when opened)
        """
        if self._stdin:
            os.close(self._stdin)
            self._stdin = None

    def __del__(self):
        """ In case someone forget to run self.close()... """
        self.close()


class Worker(object):

    """
    Abstraction to work with DockerCmd and BgJob the same way with some
    additional features like expected results handling and wait_for_start
    """

    def __init__(self, name, cmd, err=None, cname=None):
        """
        :param name: User friendly name of the worker
        :param cmd: Command
        :param err: Expected error (string or bool)
        :param cname: Container name (only for DockerCmd to map name2cname)
        """
        self.name = name
        self.cmd = cmd
        self.err = err
        self.cname = cname
        self.is_bgjob = isinstance(self.cmd, utils.BgJob)

    def __str__(self):
        """ Workaround BgJob outdated results """
        if self.is_bgjob:
            cmd = ("Command %s\nStdout:\n%s\nStderr:\n%s\nExit code: %s"
                   % (self.cmd.command, self.cmd.get_stdout(),
                      self.cmd.get_stderr(), self.cmd.sp.poll()))
        else:
            cmd = self.cmd
        return "%s:\nExpected error: %s\n%s" % (self.name, self.err, cmd)

    def output(self):
        """ Get output + stderr """
        if self.is_bgjob:
            return self.cmd.get_stdout() + self.cmd.get_stderr()
        else:
            return self.cmd.stdout + self.cmd.stderr

    def done(self):
        """ Check if process finished """
        if self.is_bgjob:
            return self.cmd.sp.poll() is not None
        else:
            if isinstance(self.cmd, InteractiveAsyncDockerCmd):
                if self.cmd.done:
                    return self.cmd.done
                else:
                    try:    # Workaround unclosed pipe docker bug...
                        self.cmd.stdin("\n")
                        time.sleep(0.1)
                    except OSError:     # Already closed...
                        pass
            return self.cmd.done

    @staticmethod
    def failif(condition, reason):
        """ Raise DockerTestFail if $condition is nonzero """
        if condition:
            raise xceptions.DockerTestFail(reason)

    def verify_started(self, timeout=10):
        """
        Wait until special message occurs.
        A) Silent 0th iteration for non-error cases
        B) Exit or err string in the output
        """
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self.err:    # Looking for error
                if self.done():
                    break
                elif (isinstance(self.err, basestring)
                      and self.err in self.output()):
                    break
            else:       # Looking for 0th iteration
                done = self.done()
                if "Silent 0th iteration" in self.output():
                    break
                self.failif(done, "Worker %s finished before 'Silent 0th "
                            "iteration'message occurred in output."
                            % self.name)
        else:
            self.failif(True, "Worker %s didn't started in %ss\n%s"
                        % (self.name, timeout, self))

    def wait_check(self, timeout):
        """ Wait for finish and check the output for errors/expected errors """
        if not self.err:
            self._wait_check_good(timeout)
        else:
            self._wait_check_bad(timeout)

    def _wait_check_good(self, timeout):
        """
        Check 'All iterations passed' string is in the output and no errors
        occurred.
        """
        res = self.wait(timeout)
        if not self.is_bgjob:     # DockerCmd, check for other failures
            OutputGood(res, skip='error_check')
        self.failif(res.exit_status, "Worker %s exit status != 0"
                    % (self.name))
        self.failif("All iterations passed" not in res.stdout, "Worker %s "
                    "finished with 0 but 'All iterations passed' not in the "
                    "output." % (self.name))
        return res

    def _wait_check_bad(self, timeout):
        """
        Check the 'All iterations passed' message is not present in the output
        and if self.err is string check it's there. Othervise just expect
        exit_status != 0.
        """
        complete = lambda: self.done() or self.err in self.output()
        utils.wait_for(complete, timeout)
        if self.done():   # Process finished, it's safe to wait_for
            res = self.wait(0)
        elif self.is_bgjob:
            # BgJob updates results only on wait_for but the process is still
            # running.
            res = self.cmd.result
            res.stdout = self.output()
        else:   # DockerCmd.cmdresult is updated automatically
            res = self.cmd.cmdresult
        output = res.stdout + res.stderr
        if isinstance(self.err, basestring) and self.err not in output:
            msg = ("Bad worker %s doesn't have '%s' message in the output."
                   % (self.name, self.err))
            raise xceptions.DockerTestFail(msg)
        elif res.exit_status == 0:
            msg = ("Bad worker %s exit status == 0" % (self.name))
            raise xceptions.DockerTestFail(msg)
        self.failif('All iterations passed' in output, "Bad worker %s output "
                    "contains 'All iterations passed' message" % self.name)
        if not self.done():
            self.wait(0)    # Kill the bastard in case it's still running

    def wait(self, timeout):
        """ Wait for the command to finish or kill it if timeout expires """
        if self.is_bgjob:
            return self.cmd.wait_for(timeout)
        elif isinstance(self.cmd, InteractiveAsyncDockerCmd):
            # Workaround unclosed pipe bug
            self.done()
            endtime = time.time() + timeout
            while time.time() < endtime:
                time.sleep(1)
                if self.done():
                    break
            return self.cmd.wait(0)
        else:
            return self.cmd.wait(timeout)


class run_ipc_mem(subtest.SubSubtestCallerSimultaneous):

    """ SubSubtest caller """

    def _copy_lib(self, library, paths):
        """
        Try to find at least one matching library and copy it into srcdir
        :param library: list of matching library names (last one shortest)
        :param paths: LD_LIBRARY_PATH as list
        :raise DockerTestNAError: When library not found (at least one math)
        """
        def find_and_copy(name, path, dst, srcdir):
            """ If not already copied and file exists, copy it """
            if dst is not None:
                src = os.path.join(path, name)
                if os.path.exists(src):
                    shutil.copy(src, os.path.join(srcdir, dst))
                    return  # Handled, remove dst
            return dst  # Not handled, return dst

        dst32 = "%s.i686" % library[-1]
        dst64 = "%s.x86_64" % library[-1]
        for name in library:
            for path in paths:
                if path.rstrip('/').endswith('64'):
                    dst64 = find_and_copy(name, path, dst64, self.srcdir)
                else:
                    dst32 = find_and_copy(name, path, dst32, self.srcdir)
                if not dst32 and not dst64:
                    return  # We are done
        if dst32:
            self.logwarning("32bit %s not found in %s, using stock one ("
                            "possibly incompatible with your system)"
                            % (library, paths))
            dst32 = find_and_copy(dst32, os.path.join(self.bindir, 'src'),
                                  dst32, self.srcdir)
        if dst64:
            self.logwarning("64bit %s not found in %s, using stock one ("
                            "possibly incompatible with your system)"
                            % (library, paths))
            dst64 = find_and_copy(dst64, os.path.join(self.bindir, 'src'),
                                  dst64, self.srcdir)
        if dst32 and dst64:
            raise xceptions.DockerTestNAError("Library %s not found in %s"
                                              % (library, paths))

    def setup(self):
        """
        Copy files which will be shared as volume in containers
        1) Find libs libraries and copy them into self.srcdir
        2) Copy shm_ping_pong testing script also to self.srcdir
        """
        # symlink libraries used in volumes
        libs = (("libc.so.6", "libc.so"), ("librt.so.1", "librt.so"))
        paths = os.environ.get('LD_LIBRARY_PATH', [])
        if paths:
            paths = paths.split(':')
        paths.extend(("/lib", "/lib32", "/usr/lib", "/usr/lib32",
                      "/usr/local/lib", "/usr/local/lib32", "/lib64",
                      "/usr/lib64", "/usr/local/lib64"))
        for lib in libs:
            self._copy_lib(lib, paths)
        # copy shm test program
        shutil.copy(os.path.join(self.bindir, 'src', 'shm_ping_pong.py'),
                    self.srcdir)

    def initialize(self):
        super(run_ipc_mem, self).initialize()
        # There is 10m timeout, use 9 minutes and 60s for timeout-less cleanup
        self.stuff['end_time'] = time.time() + 540

    def adjust_timeout(self, timeout):
        if time.time() > self.stuff['end_time']:
            return 1
        else:
            return timeout


class IpcBase(subtest.SubSubtest):

    """ Base class """

    def initialize(self):
        """
        Runs one container
        """
        super(IpcBase, self).initialize()
        # Substuff
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['containers'] = []
        self.sub_stuff['cmds'] = []
        self.sub_stuff['shms'] = []
        default_image = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['default_image'] = default_image

    @staticmethod
    def _generate_string(min_length=0, max_length=1023):
        """
        Generate random string in range of <min-max> length. For safeness
        prepend unique char to prevent partial match while shm is being
        written. (max length of shm_ping_pong segment is 1024)
        """
        return utils.generate_random_string(random.randint(min_length,
                                                           max_length))

    @staticmethod
    def _find_hosts_free_ipc(start_key):
        """ Try to find first usable shm in 1024 iterations """
        for key in xrange(start_key, start_key + 1024):
            if 'not found' in utils.run("LC_ALL=C ipcs -m -i %s" % key,
                                        10, verbose=False).stderr:
                return key
        raise xceptions.DockerTestError("Unable to find free shmmid in 1024 "
                                        "steps (starting from %s)" % start_key)

    def _exec_container(self, name, ipc, args, err=None, timeout=10):
        """
        Starts container
        :param name: User-friendly name used as reference
        :param ipc: --ipc $ipc argument
        :param args: shm_ping_pong.py arguments in form of:
                     "$shmid $no_iter $set_str $wait_for_str $cleanup[yn]"
        :param err: Expected error (bool or string)
        :param timeout: How long to wait until it's started
        """
        subargs = self.config.get('run_options_csv')
        if subargs is None:
            subargs = []
        else:
            subargs = subargs.split(',')
        subargs.append("--volume %s:/opt/ipc:rz" % self.parent_subtest.srcdir)
        if ipc:
            subargs.append("--ipc %s" % ipc)
        cname = self.sub_stuff['dc'].get_unique_name(name)
        self.sub_stuff['containers'].append(cname)
        subargs.append("--name %s" % cname)
        subargs.append(self.sub_stuff['default_image'])
        subargs.append("sh -c 'cd /opt/ipc; python shm_ping_pong.py %s; "
                       "exit $?'" % args)
        dkrcmd = AsyncDockerCmd(self, 'run', subargs, verbose=False)
        worker = Worker(name, dkrcmd, err, cname)
        self.sub_stuff['cmds'].append(worker)
        dkrcmd.execute()
        worker.verify_started(timeout)
        return cname

    '''
    def _exec_container_stdin(self, name, ipc, args, err=None, timeout=10):
        """
        Starts container
        :param ipc: --ipc $ipc argument
        :param args: shm_ping_pong.py arguments in form of:
                     "$shmid $no_iter $set_str $wait_for_str $cleanup[yn]"
        """
        subargs = self.config.get('run_options_csv')
        if subargs is None:
            subargs = []
        else:
            subargs = subargs.split(',')
        subargs.append("--volume %s:/opt/ipc:rz" % self.parent_subtest.srcdir)
        if ipc:
            subargs.append("--ipc %s" % ipc)
        cname = self.sub_stuff['dc'].get_unique_name(name)
        self.sub_stuff['containers'].append(cname)
        subargs.append("--name %s" % cname)
        subargs.append(self.sub_stuff['default_image'])
        subargs.append("sh")
        dkrcmd = InteractiveAsyncDockerCmd(self, 'run', subargs, verbose=False)
        worker = Worker(name, dkrcmd, err)
        self.sub_stuff['cmds'].append(worker)
        dkrcmd.execute("cd /opt/ipc; python shm_ping_pong.py %s || "
                       "(ipcrm -M %s && python shm_ping_pong.py %s); exit $?\n"
                       % (args, args.split(' ')[0], args))
        worker.verify_started(timeout)
        return cname
    '''     # Custom scenarios will utilize this one pylint: disable=W0105

    def _exec_host(self, name, args, err=None, timeout=10):
        """ Execute shm_ping_pong.py $args on host
        :param args: shm_ping_pong.py arguments in form of:
                     "$shmid $no_iter $set_str $wait_for_str $cleanup[yn]"
        """
        cmdline = "./shm_ping_pong.py %s" % args
        os.chdir(self.parent_subtest.srcdir)
        self.logdebug("Async-execute: Command: %s" % cmdline)
        cmd = utils.AsyncJob(cmdline, verbose=False)
        worker = Worker(name, cmd, err)
        self.sub_stuff['cmds'].append(worker)
        worker.verify_started(timeout)

    def _cleanup_containers(self):
        """ Cleanup the container """
        for name in set(self.sub_stuff.get('containers', [])):
            conts = self.sub_stuff['dc'].list_containers_with_name(name)
            if conts == []:
                return  # Docker was created, but apparently doesn't exist
            elif len(conts) > 1:
                msg = ("Multiple containers matches name %s, not removing any "
                       "of them...", name)
                raise xceptions.DockerTestError(msg)
            DockerCmd(self, 'rm', ['--force', '--volumes', name],
                      verbose=False).execute()

    def _cleanup_shm(self, key):
        """ Remove shmkey from host """
        cmd = "ipcrm -M %s" % key
        self.logdebug("Running: Command: %s" % cmd)
        utils.run(cmd, ignore_status=True, verbose=False)
        self.sub_stuff['shms'].remove(key)

    def _cleanup_shms(self):
        """ Unregister and remove the shm segment (using host) """
        for key in set(self.sub_stuff.get('shms', [])):
            self._cleanup_shm(key)

    def cleanup(self):
        """
        Log uncleanded cmds (useful for debuging) and cleanup all containers,
        shms and workers.
        """
        super(IpcBase, self).cleanup()
        try:
            # Log uncleaned workers/shms (to get better overview on error)
            if self.sub_stuff.get('cmds'):
                self.logdebug("Uncleaned workers:")
                for cmd in self.sub_stuff['cmds']:
                    self.logdebug(cmd)
            if self.sub_stuff.get('shms'):
                self.logdebug('Uncleaned IPCs: %s'
                              % self.sub_stuff.get('shms'))
            # Cleanup
            self._cleanup_containers()
            for cmd in self.sub_stuff.get('cmds', []):
                cmd.wait(0)
        finally:
            for cmd in self.sub_stuff.get('cmds', []):
                cmd.wait(0)
            self._cleanup_shms()


class AutoIpcBase(IpcBase):

    """
    Class which serves the predefined scenarios using ``setup`` config
    1. start workers using ``setup`` setup
    2. let them work
    3. check results from the last worker to the first and cleanup
    """

    def _obj_to_name(self, obj):
        """ Find container name from user-friendly name """
        for cmd in self.sub_stuff['cmds']:
            if cmd.name == obj:
                return cmd.cname
        self.failif(True, "Unable to map %s to container name, incorrect "
                    "setup '%s'" % (obj, self.config['setup']))

    def _run_setup(self, no_iter, key, setup):
        """
        Start workers according to setup. They are chained (A->B->C->...->A)
        obj = host | cont$x | $ref_cont$x
          => host = host worker, $ref = --ipc host | container:$name
        """
        string = 'a%s' % self._generate_string()
        string1 = string
        i, obj = setup.next()
        while obj:
            try:
                i2, obj2 = setup.next()     # next i=i2 pylint: disable=c0103
                string2 = '%s%s' % (chr(i + 98), self._generate_string())
                clean = 'n'
            except StopIteration:   # Last iteration uses the first string
                if clean == 'y':    # second time here...
                    break
                string2 = string1
                clean = 'y'
            if obj != 'host':
                if '_' in obj:  # ipc is defined
                    ipc, obj = obj.split('_', 1)
                else:   # No ipc
                    ipc = None
            args = ("%s %s %s %s %s" % (key, no_iter, string, string2, clean))
            err = self.config.get('%s_err' % obj, None)
            timeout = int(self.config.get('%s_start' % obj, 20))
            if obj == 'host':
                self._exec_host('host', args, err, timeout)
            else:
                if ipc and ipc != 'host':
                    ipc = "container:%s" % self._obj_to_name(ipc)
                self._exec_container(obj, ipc, args, err, timeout)
            string = string2
            i, obj = i2, obj2

    def run_once(self):
        super(AutoIpcBase, self).run_once()
        no_iter = self.config.get('no_iterations', 1024)
        key = self._find_hosts_free_ipc(random.randint(1, 65536))
        self.sub_stuff['shms'].append(key)
        setup = enumerate(self.config['setup'].split(' '))
        for setup in self.config['setup'].split('|'):
            self._run_setup(no_iter, key, enumerate(setup.strip().split(' ')))

    def postprocess(self):
        super(AutoIpcBase, self).postprocess()
        for cmd in self.sub_stuff['cmds'][::-1]:
            # Decrease the timeout in case adjust_timeout is approaching
            timeout = int(self.config.get('%s_stop' % cmd.name, 20))
            timeout = self.parent_subtest.adjust_timeout(timeout)
            cmd.wait_check(timeout)
        self.sub_stuff['shms'].pop(-1)
        del self.sub_stuff['cmds']


def auto_ipc_factory(name):
    """ Subsubclass generator for AutoIpcBase-like tests """

    class TestClass(AutoIpcBase):

        """ Dummy class inherited from AutoIpcBase renamed below """

    TestClass.__name__ = name
    return TestClass


# Generates all auto_subsubtests inherited from AutoIpcBase
__CFG = config.Config()['docker_cli/run_ipc_mem']
if __CFG.get('auto_subsubtests'):
    __GLOBALS = globals()
    for __NAME in __CFG['auto_subsubtests'].split(','):
        __GLOBALS[__NAME] = auto_ipc_factory(__NAME)
