"""
Tests the ``docker import --env`` feature.

1. Create container with couple of envs set
2. Store the ``env`` output (correctness is checked in postprocess)
3. Export the container
4. Import the container overriding and adding new envs
5. Check the ``env`` output for missing/corrupted values
"""
import os
import re
import tempfile

from autotest.client.shared import utils
from dockertest import xceptions
from dockertest.containers import DockerContainers
from dockertest.dockercmd import NoFailDockerCmd, DockerCmdBase, DockerCmd
from dockertest.images import DockerImage, DockerImages
from dockertest.subtest import SubSubtest


class with_env(SubSubtest):

    """ Subtest """

    #: Regexp matching TEST_$variable=$value
    _re_match_env = re.compile(r'\n?TEST_([^=]+)=(.+)')

    def _init_container(self, subargs, cmd, image=None):
        """ Prepare and start NoFailDockerCmd container """
        if not image:
            image = DockerImage.full_name_from_defaults(self.config)
        subargs = subargs[:]
        name = self.sub_stuff['dc'].get_unique_name()
        self.sub_stuff['containers'].add(name)
        subargs.append("--name %s" % name)
        subargs.append(image)
        subargs.append(cmd)
        dkrcmd = NoFailDockerCmd(self, 'run', subargs, verbose=False)
        dkrcmd.execute()
        return dkrcmd, name

    def _export_container(self, container):
        """ Export contianer into a new file """
        pwd = tempfile.mktemp('.tar', 'exported_container-', self.tmpdir)
        self.sub_stuff['files'].add(pwd)
        NoFailDockerCmd(self, 'export',
                        ["%s > %s" % (container[1], pwd)]).execute()
        return pwd

    def _import_container(self, subargs, pwd):
        """ Import container using $subargs and file defined by $pwd """
        image = self.sub_stuff['di'].get_unique_name()
        self.sub_stuff['images'].add(image)
        cmd = DockerCmdBase(self, 'import', subargs + ['-', image]).command
        utils.run('cat %s | %s' % (pwd, cmd))
        return image

    def initialize(self):
        def _new_envs(source):
            """
            Generate all ``status`` variables for given ``source`` in format:
            ``TEST_$DefinedFrom_$ChangedIn=$DefinedFrom``
            Where:
            *  $DefinedFrom = How the variable was set (cmdline, envfile, ...)
            *  $ChangedIn = Where this env gets overwritten
            """
            # file_unchanged=file, file_import_file=file, ...
            return ('TEST_%s_%s=%s' % (source, stat, source)
                    for stat in ('unchanged', 'import_file', 'import_cmdline',
                                 'changed_file', 'changed_cmdline',
                                 'changed_bash'))
        super(with_env, self).initialize()
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['di'] = DockerImages(self)
        self.sub_stuff['containers'] = set()
        self.sub_stuff['images'] = set()
        self.sub_stuff['files'] = set()

        subargs = self.config['run_options_csv'].split(',')
        # Env from file
        env_file_pre = tempfile.NamedTemporaryFile('w', prefix='env_pre',
                                                   dir=self.tmpdir)
        self.sub_stuff['env_file_pre'] = env_file_pre
        env_file_pre.write("\n".join(_new_envs('file')))
        env_file_pre.flush()
        subargs.append('--env-file %s' % env_file_pre.name)
        # Env on cmdline
        for env in _new_envs('cmdline'):
            subargs.append('-e %s' % env)
        # Env in container's bash
        envs = "\n".join(("export %s" % env for env in _new_envs('bash')))
        # Execute container
        cont = self._init_container(subargs, "sh -c '%s\nenv'" % envs)
        self.sub_stuff['env_pre'] = self._parse_env_from_stdout(cont[0].stdout)
        # Export container
        self.sub_stuff['exported_container'] = self._export_container(cont)

    def _parse_env_from_stdout(self, stdout):
        """
        Parses container's stdout and creates dict from all lines matching
        prescription ``TEST_$whatever=$something``.
        """
        match = self._re_match_env.findall(stdout)
        self.failif(not match, "Unable to parse container output:\n%s"
                    % stdout)
        return {key: value for key, value in match}

    def _pprint_env(self, env):
        """ print sorted dictionary (useful for recreating reference dict """
        self.logdebug("{%s}", ",\n".join('"%s": "%s"' % (key, env[key])
                                         for key in sorted(env)))

    def run_once(self):
        def _update_envs(status):
            """
            Generate variables in similar format as in ``_new_envs`` only
            with different value and this time generate all ``source`` variants
            for given status.
            """
            # file_changed_env=changed_env, cmdline_changed_env=changed_env
            return ('TEST_%s_%s=%s' % (source, status, status)
                    for source in ('file', 'cmdline', 'bash', 'new'))

        super(with_env, self).run_once()
        # Import env from file
        env_file_import = tempfile.NamedTemporaryFile('w', prefix='env_post',
                                                      dir=self.tmpdir)
        self.sub_stuff['env_file_import'] = env_file_import
        env_file_import.write("\n".join(_update_envs('import_file')))
        env_file_import.flush()
        # Import env on cmdline
        subargs = ['-e %s' % env for env in _update_envs('import_cmdline')]
        subargs.append('--env-file %s' % env_file_import.name)
        # Import the container
        image = self._import_container(subargs,
                                       self.sub_stuff['exported_container'])

        # Run the container
        subargs = self.config['run_options_csv'].split(',')
        # Env from file
        env_file_post = tempfile.NamedTemporaryFile('w', prefix='env_post',
                                                    dir=self.tmpdir)
        self.sub_stuff['env_file_post'] = env_file_post
        env_file_post.write("\n".join(_update_envs('changed_file')))
        env_file_post.flush()
        subargs.append('--env-file %s' % env_file_post.name)
        # Env on cmdline
        for env in _update_envs('changed_cmdline'):
            subargs.append('-e %s' % env)
        # Env in container's bash
        envs = "\n".join(("export %s" % env
                          for env in _update_envs('changed_bash')))
        # Execute container
        cont = self._init_container(subargs, "sh -c '%s\nenv'" % envs, image)
        # Store results
        self.sub_stuff['env'] = self._parse_env_from_stdout(cont[0].stdout)

    @staticmethod
    def _check_dicts(act, ref, msg):
        """
        Compares act and ref dictionaries and when not matching raise exception
        using given msg and adds the list of corrupted items
        """
        if act == ref:
            return
        out = ["TEST_%s=%s (%s)" % (key, val, ref.get(key, '__UNDEFINED__'))
               for key, val in act.iteritems()
               if val != ref.get(key)]
        out.extend("TEST_%s=__MISSING__ (%s)" % (key, val)
                   for key, val in ref.iteritems()
                   if key not in act)
        raise xceptions.DockerTestFail(msg % "\n".join(out))

    def postprocess(self):
        super(with_env, self).postprocess()
        # First container
        first = {"bash_changed_bash": "bash",
                 "bash_changed_cmdline": "bash",
                 "bash_changed_file": "bash",
                 "bash_import_cmdline": "bash",
                 "bash_import_file": "bash",
                 "bash_unchanged": "bash",
                 "cmdline_changed_bash": "cmdline",
                 "cmdline_changed_cmdline": "cmdline",
                 "cmdline_changed_file": "cmdline",
                 "cmdline_import_cmdline": "cmdline",
                 "cmdline_import_file": "cmdline",
                 "cmdline_unchanged": "cmdline",
                 "file_changed_bash": "file",
                 "file_changed_cmdline": "file",
                 "file_changed_file": "file",
                 "file_import_cmdline": "file",
                 "file_import_file": "file",
                 "file_unchanged": "file"}

        env = self.sub_stuff['env_pre']
        # self._pprint_env(env)
        self._check_dicts(env, first, "Environment of the first container"
                          " is not the same as expected:\n%s")

        second = {"bash_changed_bash": "changed_bash",
                  "bash_changed_cmdline": "changed_cmdline",
                  "bash_changed_file": "changed_file",
                  "bash_import_cmdline": "import_cmdline",
                  "bash_import_file": "import_file",
                  "cmdline_changed_bash": "changed_bash",
                  "cmdline_changed_cmdline": "changed_cmdline",
                  "cmdline_changed_file": "changed_file",
                  "cmdline_import_cmdline": "import_cmdline",
                  "cmdline_import_file": "import_file",
                  "file_changed_bash": "changed_bash",
                  "file_changed_cmdline": "changed_cmdline",
                  "file_changed_file": "changed_file",
                  "file_import_cmdline": "import_cmdline",
                  "file_import_file": "import_file",
                  "new_changed_bash": "changed_bash",
                  "new_changed_cmdline": "changed_cmdline",
                  "new_changed_file": "changed_file",
                  "new_import_cmdline": "import_cmdline",
                  "new_import_file": "import_file"}
        env = self.sub_stuff['env']
        # self._pprint_env(env)
        self._check_dicts(env, second, "Environment of imported container "
                          "is not the same as expected:\n%s")

    def _cleanup_containers(self):
        """
        Cleanup the container
        """
        for name in self.sub_stuff.get('containers', []):
            conts = self.sub_stuff['dc'].list_containers_with_name(name)
            if conts == []:
                return  # Docker was created, but apparently doesn't exist
            elif len(conts) > 1:
                msg = ("Multiple containers matches name %s, not removing any "
                       "of them...", name)
                raise xceptions.DockerTestError(msg)
            DockerCmd(self, 'rm', ['--force', '--volumes', name],
                      verbose=False).execute()

    def _cleanup_images(self):
        """
        Cleanup the images defined in self.sub_stuff['images']
        """
        images = self.sub_stuff['di']
        all_imgs = (images.list_imgs_full_name())
        for image in self.sub_stuff["images"]:
            if ':' not in image:
                image += ':latest'
            if image not in all_imgs:
                continue    # Image already removed
            try:
                self.logdebug("Removing testing image %s", image)
                images.remove_image_by_full_name(image)
            except xceptions.AutotestError, exc:
                self.logerror("Failure while removing image %s:\n%s",
                              image, exc)

    def _cleanup_files(self):
        """ Unlink all used cidfiles """
        for name in self.sub_stuff.get('files', []):
            if os.path.exists(name):
                os.unlink(name)
        for attr in ('env_file_pre', 'env_file_import', 'env_file_post'):
            if attr in self.sub_stuff:
                self.sub_stuff[attr].close()

    def cleanup(self):
        super(with_env, self).cleanup()
        self._cleanup_containers()
        self._cleanup_images()
        self._cleanup_files()
