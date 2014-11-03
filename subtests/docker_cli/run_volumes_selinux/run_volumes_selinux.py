"""
Summary
-------

Tests the --volume ::Z feature (automatic selinux context setting).


Operational Summary
-------------------

1.  Start container using volume with z/Z set
2.  Check context and file creation within the container
3.  Start another container --volumes-from $cont1
4.  Check context and file creation
5.  Try writing using $cont1
6.  Verify (only) all created files are present
"""
import os
import re
import shutil
import tempfile
import time

from autotest.client.shared import utils
from dockertest import config, xceptions, subtest, dockercmd, environment
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage


try:
    import selinux
except ImportError:
    if utils.run("selinuxenabled", 10, True).exit_status:
        raise xceptions.DockerTestNAError("Selinux not enabled on this "
                                          "machine.")
    else:
        raise


def set_selinux_context(pwd, context=None, recursive=True):
    """ Wrapper around environment.set_selinux_context """
    return environment.set_selinux_context(pwd, context, recursive)


def get_selinux_context(pwd):
    """ Wrapper around selinux to set selinux context """
    return selinux.getfilecon(pwd)[1]


class InteractiveAsyncDockerCmd(dockercmd.AsyncDockerCmd):

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


class Output(object):

    """
    Wraps object with `.stdout` method and returns only new chars out of it
    """

    def __init__(self, stuff, idx=None):
        self.stuff = stuff
        if idx is None:
            self.idx = len(stuff.stdout.splitlines())
        else:
            self.idx = idx

    def get(self, idx=None):
        """
        :param idx: Override last index
        :return: Output of stuff.stdout from idx (or last read)
        """
        if idx is None:
            idx = self.idx
        out = self.stuff.stdout.splitlines()
        self.idx = len(out)
        return out[idx:]

    def read_until_regexp(self, regexp, timeout=60):
        """
        Read until regexp matches the output line (only single line!)
        :param regexp: re.compile() version of regexp
        :param timeout: timeout
        """
        idx = self.idx
        end = time.time() + timeout
        while True:
            out = self.get()    # Get only new input
            for line in out:
                if regexp.match(line):
                    match = regexp.match(line).groups()
                    return match, "\n".join(self.get(idx))    # Get full output
            time.sleep(0.1)
            if time.time() > end:
                break
        raise IOError("Timeout while looking for %s. Output so far:\n%s"
                      % (regexp.pattern, out))


class run_volumes_selinux(subtest.SubSubtestCaller):

    """ SubSubtest caller """


class selinux_base(subtest.SubSubtest):

    """ Base class """

    def initialize(self):
        """
        Runs one container
        """
        super(selinux_base, self).initialize()
        if utils.run("selinuxenabled", 10, True).exit_status:
            raise xceptions.DockerTestNAError("Selinux not enabled on this "
                                              "machine.")
        # Substuff
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['containers'] = []
        self.sub_stuff['volumes'] = set()

    def _init_container(self, volume=False, volumes_from=False):
        """
        Starts container
        :warning: When dkrcmd_cls is of Async type, there is no guarrantee
                  that it is going to be up&running after return.
        """
        subargs = [arg for arg in
                   self.config['run_options_csv'].split(',')]
        if volume:
            subargs.append("--volume %s" % volume)
        if volumes_from:
            subargs.append("--volumes-from %s" % volumes_from)
        name = self.sub_stuff['dc'].get_unique_name()
        self.sub_stuff['containers'].append(name)
        subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append("sh")
        dkrcmd = InteractiveAsyncDockerCmd(self, 'run', subargs)
        dkrcmd.execute()
        return dkrcmd, Output(dkrcmd), name

    def _check_context_recursive(self, path, context):
        """ Check all files in given $path have the context $context """
        for pwd, _, filenames in os.walk(path):
            for filename in filenames:
                act = get_selinux_context("%s/%s" % (pwd, filename))
                self.failif(act != context, "Context of file %s is not %s (%s)"
                            % ("%s/%s" % (pwd, filename), context, act))

    def _init_volume(self, context):
        """
        Create new dir on host, put a file in it, set $context context
        recursively and check it was set properly.
        :param context: Desired volume context
        :return: path to new directory
        """
        volume = tempfile.mkdtemp(prefix='volume', dir=self.tmpdir)
        self.sub_stuff['volumes'].add(volume)
        host_file = os.path.join(volume, "hostfile")
        open(host_file, 'w').write("01")
        set_selinux_context(volume, context, True)
        _context = get_selinux_context(volume)
        self.failif(context not in _context, "Newly set context was not set "
                    "properly (set %s, get %s)" % (context, _context))
        self._check_context_recursive(volume, _context)
        return volume

    def _touch_and_check(self, cont, volume, filename, context_pre,
                         should_fail, context_eq):
        """
        Touch file $filename using $cont, check it passed/fail and then verify
        context is (not) the same as $context_pre. Also verify all files have
        the same context.
        :param cont: (dkrcmd, dkrcmd_output, container_name)
        :param volume: Path to shared volume (on host)
        :param filename: filename to touch on guest (relative to shared volume)
        :param context_pre: Reference context
        :param should_fail: Should the file creation fail?
        :param context_eq: Should the context be equal to reference one?
        :return: new context
        """
        time.sleep(0.5)
        self.logdebug("Touching /tmp/test/%s in container %s"
                      % (filename, cont[2]))
        cont[0].stdin("touch /tmp/test/%s\necho RET: $?\n" % filename)
        match, out = cont[1].read_until_regexp(re.compile(r'RET: (\d+)$'))
        if should_fail:
            self.failif(not int(match[0]), "File creation passed unexpectedly:"
                        "\n%s" % out)
        else:
            self.failif(int(match[0]), "Unable to create file:\n%s" % out)
        context_post = get_selinux_context(volume)
        if context_eq:
            self.failif(context_pre != context_post, "Selinux context is not"
                        "%s (%s)" % (context_pre, context_post))
        else:
            self.failif(context_pre == context_post, "Selinux context had not "
                        "change (%s)." % context_post)
        self._check_context_recursive(volume, context_post)
        return context_post

    def _check_all_files(self, volume, exp_files):
        """
        Check only exp_files are present in volume
        :param volume: path to shared volume dir (on host)
        :param exp_files: expected files (relative to volume)
        """
        exp_files = set('%s/%s' % (volume, _) for _ in exp_files)
        act_files = set()
        for pwd, _, filenames in os.walk(volume):
            for filename in filenames:
                act_files.add('%s/%s' % (pwd, filename))
        self.failif(exp_files.symmetric_difference(act_files), "Not all files"
                    "present in volume:\nDiff: %s\nAct: %s\nExp: %s"
                    % (exp_files.symmetric_difference(act_files), act_files,
                       exp_files))

    def _cleanup_containers(self):
        """ Cleanup the container """
        for name in self.sub_stuff.get('containers', []):
            conts = self.sub_stuff['dc'].list_containers_with_name(name)
            if conts == []:
                return  # Docker was created, but apparently doesn't exist
            elif len(conts) > 1:
                msg = ("Multiple containers matches name %s, not removing any "
                       "of them...", name)
                raise xceptions.DockerTestError(msg)
            dockercmd.DockerCmd(self, 'rm', ['--force', '--volumes', name],
                                verbose=False).execute()

    def _cleanup_volumes(self):
        """ Remove all used volumes on host """
        for name in self.sub_stuff.get('volumes', []):
            if os.path.exists(name):
                shutil.rmtree(name)

    def cleanup(self):
        super(selinux_base, self).cleanup()
        self._cleanup_containers()
        self._cleanup_volumes()


class shared(selinux_base):

    """
    Uses flags ``rwz``, which should share volume along all conts
    """

    def run_once(self):
        super(shared, self).run_once()
        # Prepare a volume
        volume_dir = self._init_volume(self.config['selinux_host'])
        context0 = get_selinux_context(volume_dir)
        # Start first container
        volume = "%s:/tmp/test:rwz" % volume_dir
        cont1 = self._init_container(volume)
        context1 = self._touch_and_check(cont1, volume_dir, 'guest1', context0,
                                         False, False)
        # Start second container
        cont2 = self._init_container(None, cont1[2])
        context2 = self._touch_and_check(cont2, volume_dir, 'guest2', context1,
                                         False, True)
        # Create another one from first container
        self._touch_and_check(cont1, volume_dir, 'guest1_2', context2,
                              False, True)
        self._check_all_files(volume_dir, ('hostfile', 'guest1', 'guest2',
                                           'guest1_2'))


class private(selinux_base):

    """
    Uses flags ``rwZ``, which should restrict volume only to the last created
    container
    """

    def run_once(self):
        super(private, self).run_once()
        # Prepare a volume
        volume_dir = self._init_volume(self.config['selinux_host'])
        context0 = get_selinux_context(volume_dir)
        # Start first container
        volume = "%s:/tmp/test:rwZ" % volume_dir
        cont1 = self._init_container(volume)
        context1 = self._touch_and_check(cont1, volume_dir, 'guest1', context0,
                                         False, False)
        # Start second container
        cont2 = self._init_container(None, cont1[2])
        context2 = self._touch_and_check(cont2, volume_dir, 'guest2', context1,
                                         False, False)
        # Create another one from first container
        self._touch_and_check(cont1, volume_dir, 'guest1_2', context2,
                              True, True)
        self._check_all_files(volume_dir, ('hostfile', 'guest1', 'guest2'))
