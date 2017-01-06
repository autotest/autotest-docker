"""
Summary
-------

Tests the --volume ::Z and ::z feature (automatic selinux context setting).


Operational Summary
-------------------

1.  Start container using volume with z or Z set
2.  Check context and file creation within the container
3.  Start another container --volumes-from $first_container
4.  Verify context and file creation from first, second, and host
"""

import os
import shutil
import tempfile
from autotest.client.shared import utils
from dockertest import config
from dockertest import xceptions
from dockertest import subtest
from dockertest import dockercmd
from dockertest.environment import set_selinux_context
from dockertest.environment import get_selinux_context
from dockertest.output import wait_for_output
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage


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
            raise xceptions.DockerTestNAError("Selinux not enabled on this"
                                              " machine.")
        # Substuff
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['containers'] = []
        self.sub_stuff['volumes'] = set()
        self.sub_stuff['fds'] = []

    def init_container(self, volume=None, volumes_from=None):
        """
        Starts container
        """
        subargs = config.get_as_list(self.config['run_options_csv'])
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
        read_fd, write_fd = os.pipe()
        self.sub_stuff['fds'].append(write_fd)
        self.sub_stuff['fds'].append(read_fd)
        dkrcmd = dockercmd.AsyncDockerCmd(self, 'run', subargs)
        # TODO: Fix use of dkrcmd.stdin when appropriate class mech. available
        dkrcmd.execute(read_fd)
        dkrcmd.stdin = write_fd
        os.close(read_fd)  # no longer needed
        os.write(write_fd, 'echo "Started"\n')
        self.failif(not wait_for_output(lambda: dkrcmd.stdout,
                                        'Started',
                                        timeout=20),
                    "Error starting container %s: %s" % (name, dkrcmd))
        return dkrcmd

    def check_context_recursive(self, path, context):
        """ Check all files in given $path have the context $context """
        for pwd, _, filenames in os.walk(path):
            for filename in filenames:
                act = get_selinux_context("%s/%s" % (pwd, filename))
                self.logdebug("File %s Context: %s",
                              os.path.join(pwd, filename),
                              act)
                self.failif_ne(act, context, "Context of file %s/%s"
                               % (pwd, filename))

    def init_volume(self, context):
        """
        Create new dir on host, put a file in it, set $context context
        recursively and check it was set properly.
        :param context: Desired volume context
        :return: path to new directory
        """
        if self.config['use_system_tmp']:
            tmp = '/var/tmp'
        else:
            tmp = self.tmpdir
        volume = tempfile.mkdtemp(prefix=self.__class__.__name__, dir=tmp)
        self.sub_stuff['volumes'].add(volume)
        host_file = os.path.join(volume, "hostfile")
        open(host_file, 'w').write("01")
        set_selinux_context(volume, context, True)
        _context = get_selinux_context(volume)
        self.failif(context not in _context, "Newly set context was not set"
                    " properly (set %s, get %s)" % (context, _context))
        self.check_context_recursive(volume, _context)
        return volume

    def touch_and_check(self, cont, volume, filename, context_pre,
                        should_fail, context_eq):
        """
        Touch file $filename using $cont, check it passed/fail and then verify
        context is (not) the same as $context_pre. Also verify all files have
        the same context.
        :param cont: dkrcmd instance
        :param volume: Path to shared volume (on host)
        :param filename: filename to touch on guest (relative to shared volume)
        :param context_pre: Reference context
        :param should_fail: Should the file creation fail?
        :param context_eq: Should the context be equal to reference one?
        :return: new context
        """
        self.logdebug("Volume: %s Context: %s", volume,
                      get_selinux_context(volume))
        self.logdebug("Touching /tmp/test/%s in container"
                      % filename)
        # Some filesystems don't synchronize directory cache flushes if
        # pagecache for a file isn't also dirty.  Always updating
        # content is easier that checking filesystem from inside a container.
        os.write(cont.stdin, "date > /tmp/test/%s\necho RET: $?\n" % filename)
        match = wait_for_output(lambda: cont.stdout, r'RET:\s+0$', timeout=10)
        if should_fail:
            self.failif(match, "File creation passed unexpectedly:"
                               "\n%s" % cont.stdout)
        else:
            self.failif(not match,
                        "Unable to create file:\n%s"
                        % cont.stdout)
        context_post = get_selinux_context(volume)
        if context_eq:
            self.failif_ne(context_post, context_pre, "Selinux context")
        else:
            self.failif(context_pre == context_post,
                        "Selinux context had not "
                        "change (%s)." % context_post)
        self.check_context_recursive(volume, context_post)
        return context_post

    def check_all_files(self, volume, exp_files):
        """
        Check only exp_files are present in volume
        :param volume: path to shared volume dir (on host)
        :param exp_files: expected files (relative to volume)
        """
        # Make sure disk matches pagecache
        # (See also, os.write() comment in touch_and_check())
        utils.run("sync", 10)
        exp_files = set('%s/%s' % (volume, _) for _ in exp_files)
        act_files = set()
        for pwd, _, filenames in os.walk(volume):
            for filename in filenames:
                act_files.add('%s/%s' % (pwd, filename))
        self.failif(exp_files.symmetric_difference(act_files), "Not all files"
                    " present in volume:\nDiff: %s\nAct: %s\nExp: %s"
                    % (exp_files.symmetric_difference(act_files), act_files,
                       exp_files))

    def cleanup(self):
        super(selinux_base, self).cleanup()
        for fd in self.sub_stuff.get('fds', []):
            try:
                os.close(fd)
            except OSError:
                pass  # closing was the goal
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            dc.clean_all(self.sub_stuff.get("containers", []))
        for name in self.sub_stuff['volumes']:
            if os.path.exists(name):
                shutil.rmtree(name)


class shared(selinux_base):

    """
    Uses flags ``z``, which should share volume along all conts
    """

    def run_once(self):
        super(shared, self).run_once()
        # Prepare a volume
        volume_dir = self.init_volume(self.config['selinux_host'])
        context0 = get_selinux_context(volume_dir)
        # Start first container
        cont1 = self.init_container("%s:/tmp/test:z" % volume_dir)
        context1 = self.touch_and_check(cont1, volume_dir, 'guest1', context0,
                                        False, False)
        # Start second container
        cont2 = self.init_container("%s:/tmp/test" % volume_dir)
        context2 = self.touch_and_check(cont2, volume_dir, 'guest2', context1,
                                        False, True)
        # Create another one from first container
        self.touch_and_check(cont1, volume_dir, 'guest1_2', context2,
                             False, True)
        self.check_all_files(volume_dir, ('hostfile', 'guest1', 'guest2',
                                          'guest1_2'))


class private(selinux_base):

    """
    Uses flags ``Z``, which should restrict volume only to the last created
    container
    """

    def run_once(self):
        super(private, self).run_once()
        # Prepare a volume
        volume_dir = self.init_volume(self.config['selinux_host'])
        context0 = get_selinux_context(volume_dir)
        # Start first container
        cont1 = self.init_container("%s:/tmp/test:Z" % volume_dir)
        context1 = self.touch_and_check(cont1, volume_dir, 'guest1', context0,
                                        False, False)
        # Start second container
        cont2 = self.init_container("%s:/tmp/test" % volume_dir)
        self.touch_and_check(cont2, volume_dir, 'guest2', context1,
                             True, True)
        # Create another one from first container
        self.touch_and_check(cont1, volume_dir, 'guest1_2', context1,
                             False, True)
        self.check_all_files(volume_dir, ('hostfile', 'guest1', 'guest1_2'))
