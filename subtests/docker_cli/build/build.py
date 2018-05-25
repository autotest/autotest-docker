r"""
Summary
----------

Tests the ``docker build`` command operation with various options
and pre-defined build-content, both local and remote.

Operational Summary
--------------------

#. Gather source files if not done previously
#. Gather all test and command options for each build
#. Run all builds
#. Check build exit code, output, images, and containers are expected.

Prerequisites
----------------

*  Behavior in Dockerfiles match expected behavior of sub-subtest & config.
"""

import os.path
import re
import shutil
from collections import namedtuple
from dockertest.subtestbase import SubBase
from dockertest import subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.output import OutputGood
from dockertest.output import OutputNotBad
from dockertest.output import DockerVersion
from dockertest.config import get_as_list
from dockertest.xceptions import DockerTestFail
from dockertest.xceptions import DockerTestError


class BuildBase(SubBase):
    """
    Shared base-class for ``build`` and ``BuildSubSubtest``
    """

    def initialize(self):
        super(BuildBase, self).initialize()
        self.reset_build_context()
        self.stuff['dc'] = dcont = DockerContainers(self)
        self.stuff['existing_containers'] = dcont.list_container_ids()
        self.stuff['di'] = dimg = DockerImages(self)
        self.stuff['existing_images'] = ei = dimg.list_imgs()
        self.logdebug("Existing images: %s", ei)

    def reset_build_context(self):
        """
        Fixup source dir at end of testing to leave it clean for next time.
        """
        source_dirs = self.config['source_dirs']
        for dir_path in get_as_list(source_dirs):
            if isinstance(self, subtest.SubSubtest):
                _self = self.parent_subtest
            else:
                _self = self
            # bindir is location of this module
            src = os.path.join(_self.bindir, dir_path)
            # srcdir is recreated if doesn't exist or if test version changes
            dst = os.path.join(_self.srcdir, dir_path)
            src = os.path.abspath(src)
            dst = os.path.abspath(dst)
            self.failif(len(dst) < 5,
                        "Destination dir %s seems too short" % dst)
            self.failif(len(src) < 5,
                        "Source dir %s seems too short" % src)
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)

    def cleanup(self):
        super(BuildBase, self).cleanup()
        if self.config['remove_after_test']:
            dc = self.stuff.get('dc')
            if dc:
                dc.clean_all(dc.list_container_names())
            di = self.stuff.get('di')
            if di:
                to_clean = di.list_imgs_full_name()
                to_clean += [img.long_id for img in di.list_imgs()
                             if img.full_name.strip() == '']
                di.clean_all(to_clean)


class build(BuildBase, subtest.SubSubtestCaller):
    pass


class postprocessing(object):

    """Mixin class for BuildSubSubtest to contain postprocessing methods"""

    RE_IMAGES = re.compile(r'\s*-+>\s*(\w{64}|\w{12})', re.MULTILINE)
    RE_CONTAINERS = re.compile(r's*-+>\s*Running in\s*(\w{64}|\w{12})',
                               re.MULTILINE)
    RE_CSVCMD = re.compile(r"(\S+)\(('.*')?\)")

    def postprocess(self):
        super(postprocessing, self).postprocess()
        # Debug output from all checks may be useful, run them all
        # but fail test if any are false
        passed = []  # True/False results from postprocess_commands
        for build_def in self.sub_stuff['builds']:
            postprocess_commands = self.parse_postprocess_commands(build_def)
            for method, args in postprocess_commands:
                build_def = args[0]
                command = args[1]
                parameter = args[2]
                result = method(build_def, command, parameter)
                passed.append(result)
                if not result:
                    self.logwarning("Postprocess %s: Failed", command)
        if not all(passed):
            raise DockerTestFail("One or more postprocess commands did not"
                                 " pass, see debug log for details")
        else:
            self.loginfo("All postprocessing passed")

    @property
    def postproc_cmd_map(self):
        """
        Represent mapping of postprocess commands to instance methods.

        Each method will be called with buildobj, the command, and it's string
        parameter.  Each should return True/False if the check passed or
        failed.
        """
        # As a property, instance bound methods can be returned
        # and mapping can be overriden by subclasses.
        return {
            'positive': self.basic_postprocess,
            'negative': self.basic_postprocess,
            'rx_out': self.regex_postprocess,
            '!rx_out': self.regex_postprocess,
            'rx_err': self.regex_postprocess,
            '!rx_err': self.regex_postprocess,
            'img_count': self.count_postprocess,
            'cnt_count': self.count_postprocess,
            'last_cnt': self.last_postprocess,
            'img_exst': self.created_image_postprocess,
            '!img_exst': self.created_image_postprocess,
            'intr_exst': self.intermediate_exist_postprocess,
            '!intr_exst': self.intermediate_exist_postprocess,
            'dir_exist': self.filedir_contents_postprocess,
            '!dir_exist': self.filedir_contents_postprocess,
            'file_exist': self.filedir_contents_postprocess,
            '!file_exist': self.filedir_contents_postprocess,
            'rx_file': self.filedir_contents_postprocess,
            '!rx_file': self.filedir_contents_postprocess,
        }

    def parse_postprocess_commands(self, build_def):
        """
        Parse raw postproc_cmd_csv ordered list of callables + arguments

        Any postproc_cmd that does not map, will be ignored.
        """
        result = []
        commands = []
        for command_param in get_as_list(build_def.postproc_cmd_csv):
            if not command_param:
                continue
            mobj = self.RE_CSVCMD.search(command_param)
            if not mobj:
                self.logwarning("Ignoring malformed post-process command %s",
                                command_param)
                continue
            # empty group item defaults to None
            command, param = mobj.groups()
            if command:
                command = command.strip()
            if param:
                param = param.strip()
            # String parameter MUST be enclosed in "'" quotes so
            # it may contain (,) characters in regular expressions
            # if needed.
            if param and param[0] == "'" and param[-1] == "'":
                param = param[1:-1]  # strip off quote characters
            elif param:
                self.logwarning("Invalid postprocess command parameter "
                                "syntax (missing single-quotes?): %s",
                                param)
                param = None
            else:
                param = None  # just for clarity
            try:
                method = self.postproc_cmd_map[command]
            except KeyError:
                self.logerror("Unknown postprocessing command: %s", command)
                raise
            # Special case for 'docker=this and that;podman=something else'
            if param and 'podman=' in param:
                tool_dict = {}
                for tool_value in param.split(';'):
                    (tool, value) = tool_value.split('=')
                    tool_dict[tool] = value
                if DockerVersion().is_podman:
                    param = tool_dict['podman']
                else:
                    param = tool_dict['docker']
            args = (build_def, command, param)
            result.append((method, args))
            commands.append(command)
        self.logdebug("Postprocessing commands: %s", commands)
        return result

    def basic_postprocess(self, build_def, command, parameter):
        del parameter  # not used
        # June 2017: docker-1.13 ignores $TERM for build sub-command.
        #            Jambs ANSI codes in output, BZ1403326
        skip = ['nonprintables_check']
        if self.config['enable_nonprintables_check']:
            skip = None
        if command == 'positive':
            # Verify zero exit status and healthy output
            opg = OutputGood(build_def.dockercmd.cmdresult,
                             skip=skip, ignore_error=True)
            if opg:
                return build_def.dockercmd.cmdresult.exit_status == 0
            self.logwarning('Positive output expected but check'
                            ' failed: %s', str(opg))
            return False
        elif command == 'negative':
            # Verify non-zero exit status and no panics
            notbad = OutputNotBad(build_def.dockercmd.cmdresult,
                                  skip=skip, ignore_error=True)
            if notbad:
                return build_def.dockercmd.cmdresult.exit_status != 0
            self.logwarning('Negative output expected, but'
                            ' this is worse: %s', str(notbad))
            return False
        else:
            raise DockerTestError("Command error: %s" % command)

    def regex_postprocess(self, build_def, command, parameter):
        if command not in ('rx_out', '!rx_out', 'rx_err', '!rx_err'):
            raise DockerTestError("Command error: %s" % command)
        if command.endswith('_out'):
            output = build_def.dockercmd.stdout
        else:
            output = build_def.dockercmd.stderr
        mobj = re.search(parameter, output, re.MULTILINE)
        if command.startswith('rx'):
            self.logdebug("%s(%s) Matched regex: %s", command,
                          parameter, bool(mobj))
            return bool(mobj)  # matched at least one line
        # must not match
        self.logdebug("%s(%s) Not-matched regex: %s", command,
                      parameter, not bool(mobj))
        return not bool(mobj)  # matched on any line

    def count_postprocess(self, build_def, command, parameter):
        del build_def  # not used
        expected = int(parameter)
        if command == 'img_count':
            word = 'images'
            before = len(self.sub_stuff['existing_images'])
            after = len(self.sub_stuff['di'].list_imgs())
        elif command == 'cnt_count':
            word = 'containers'
            before = len(self.sub_stuff['existing_containers'])
            after = len(self.sub_stuff['dc'].list_containers())
        else:
            raise DockerTestError("Command error: %s" % command)
        diff = after - before
        self.logdebug("%s() Found %d additional %s", command, diff, word)
        self.logdebug("%s() Expecting to find %d", command, expected)
        return diff == expected

    def _all_images(self):
        di = self.sub_stuff['di']
        di.images_args += " --all"    # list all
        images = di.list_imgs()
        # Set arguments back to default
        di.images_args = DockerImages.images_args
        return images

    def created_image_postprocess(self, build_def, command, parameter):
        del parameter  # not used
        if command not in ('img_exst', '!img_exst'):
            raise DockerTestError("Command error: %s" % command)
        images = self._all_images()
        # Search all images, ignore unknown (None) name components
        self.logdebug("%s() current images:\n%s", command,
                      '\n'.join([img.full_name
                                 for img in images
                                 if img.full_name]))
        matches = [img
                   for img in images
                   if img.cmp_greedy_full_name(build_def.image_name)]
        self.logdebug("%s() Matched %d", command, len(matches))
        if command == 'img_exst':
            if len(matches) != 1:
                return False
        else:  # negative test
            if matches:
                return False
        return True

    def intermediate_exist_postprocess(self, build_def, command, parameter):
        del parameter  # not used
        if command not in ('intr_exst', '!intr_exst'):
            raise DockerTestError("Command error: %s" % command)
        stderr = build_def.dockercmd.stderr  # make name shorter
        created_ids = [mobj.group(1)
                       for mobj in self.RE_IMAGES.finditer(stderr)
                       if mobj is not None]
        self.logdebug("%s() Intermediate images created: %d",
                      command, len(created_ids))
        created_ids = set(created_ids)
        img_ids = set([img.short_id for img in self._all_images()])
        if command == 'intr_exst':
            # Every ID in created_ids must be in img_ids
            if created_ids.issubset(img_ids):
                self.logdebug("%s() All accounted for", command)
                return True
        else:  # No iD must be in img_ids
            if created_ids.isdisjoint(img_ids):
                self.logdebug("%s() All missing as expected", command)
                return True
        self.logdebug("%s() Unaccounted intermediates: %s",
                      command, created_ids)
        self.logdebug("w/ leftover image IDs: %s", img_ids)
        return False

    def last_postprocess(self, build_def, command, parameter):
        del parameter  # not used
        if command != 'last_cnt':
            raise DockerTestError("Command error: %s" % command)
        dc = self.sub_stuff['dc']
        containers = [cid[0:12] for cid in dc.list_container_ids()]
        stderr = build_def.dockercmd.stderr.strip()
        created_containers = [mobj.group(1)
                              for mobj in self.RE_CONTAINERS.finditer(stderr)
                              if mobj is not None]
        self.logdebug("%s() Intermediate containers: %d",
                      command, len(created_containers))
        # Only last one should be present, fail if any others
        for cid in created_containers[:-1]:  # All except last one
            if cid in containers:
                self.logdebug("%s() Intermediate container found after build",
                              command)
                return False
        # Last container must be present
        if created_containers and created_containers[-1] not in containers:
            self.logdebug("%s() Last container not found after build", command)
            return False
        self.logdebug("%s() Last container accounted for", command)
        return True  # pass

    def filedir_contents_postprocess(self, build_def, command, parameter):
        bad_command = [command.find('file_exist') < 0,
                       command.find('dir_exist') < 0,
                       command.find('rx_file') < 0]
        if all(bad_command):
            raise DockerTestError('Command error: %s' % command)

        positive = command[0] != '!'
        # Need a character unlikely in file name
        params = get_as_list(parameter, ':')
        path = params[0]
        try:
            regex = re.compile(''.join(params[1:]))
        except IndexError:  # parameter not specified
            regex = None

        # Only cmd differs between all commands (file, dir, rx).
        if command.find('file') > -1:
            cmd = 'cat "%s"' % path
        else:
            cmd = 'ls -la "%s"' % path
        subargs = ['--rm', '--attach', 'stdout', build_def.image_name, cmd]
        dkrcmd = DockerCmd(self, 'run', subargs)
        dkrcmd.quiet = True
        dkrcmd.execute()
        exists = dkrcmd.exit_status == 0
        self.logdebug('%s(%s) exists: %s', command, path, exists)
        if command.find('exist') > -1:
            return positive == exists
        if not exists:
            return False  # guaranteed failure, don't bother searching
        contents = dkrcmd.stdout.strip()
        mobj = regex.search(contents)
        self.logdebug('%s(%s) matches: %s', command, regex.pattern, bool(mobj))
        return positive == bool(mobj)


class BuildSubSubtest(BuildBase, postprocessing, subtest.SubSubtest):

    # Search/Replace un-commented FROM line(s) in Dockerfile
    FROM_REGEX = re.compile(r'^FROM\s+.*', re.IGNORECASE | re.MULTILINE)

    # Generate named tuple class to hold fixed build parameters
    BuildDef = namedtuple('BuildDef',
                          ['image_name',           # Name of image to build
                           'dockercmd',            # Execution state
                           'use_config_repo',      # True/False
                           'dockerfile_dir_path',  # path / url / git repo
                           'minus_eff',            # None, or ``-f`` opt. val.
                           'base_repo_fqin',       # Substitute for FROM
                           'postproc_cmd_csv'])    # CSV of postprocess steps

    def dockerfile_dir_path(self, dir_path):
        if not isinstance(dir_path, basestring) or dir_path is None:
            return dir_path
        if dir_path[0] == '/':
            srcdir = self.parent_subtest.srcdir
            # Skip leading '/', append to source dir from setup()
            abs_dir_path = os.path.join(srcdir, dir_path[1:])
            if os.path.isdir(abs_dir_path):
                return abs_dir_path
            # else, fall through, return un-modified dir_path
        return dir_path

    def dockerfile_replace_line(self, dockerfile_path, from_regex, with_str):
        dockerfile = ''
        with open(dockerfile_path, 'r') as dockerfile_old:
            dockerfile = dockerfile_old.read()
        dockerfile = from_regex.sub(with_str, dockerfile)
        with open(dockerfile_path, 'w+b') as dockerfile_new:
            dockerfile_new.write(dockerfile)
        file_name = os.path.basename(dockerfile_path)
        self.logdebug("Updated %s:", file_name)
        self.logdebug(dockerfile)

    def dockerfile_repo_replace(self, dockerfile_path, with_repo):
        with_str = ('FROM %s' % with_repo)
        self.dockerfile_replace_line(dockerfile_path,
                                     self.FROM_REGEX, with_str)

    def make_builds(self, source):
        dimg = self.sub_stuff['di']
        image_name = dimg.get_unique_name()
        base_repo_fqin = DockerImage.full_name_from_defaults(source)
        # Existing images recorded after this method runs
        DockerCmd(self, 'pull', [base_repo_fqin]).execute()
        use_config_repo = source['use_config_repo']
        postproc_cmd_csv = source['postproc_cmd_csv']
        dockerfile_dir_path = source['dockerfile_dir_path'].strip()
        # Only replace w/ abs-path if dockerfile_dir_path starts with '/'
        # and if the abs-path points to an existing directory
        dockerfile_dir_path = self.dockerfile_dir_path(dockerfile_dir_path)
        # Use default 'Dockerfile' or custom -f option
        minus_eff = source['minus_eff']
        if minus_eff is not None and minus_eff.strip() != '':
            minus_eff = minus_eff.strip()
        else:
            minus_eff = None
        if use_config_repo:  # Indicates NOT a url / git repo
            if minus_eff is not None:
                dockerfile = minus_eff
            else:
                dockerfile = 'Dockerfile'
            # Form full path including "Dockerfile"
            full_dockerfile_path = os.path.join(dockerfile_dir_path,
                                                dockerfile)
            self.dockerfile_repo_replace(full_dockerfile_path,
                                         base_repo_fqin)
        # else:  dockerfile_dir_path is a url or git repo, read-only
        docker_build_options = source['docker_build_options'].strip()
        docker_build_options = get_as_list(docker_build_options)
        if minus_eff is not None:
            docker_build_options += ['-f', minus_eff]
            #  Workaround BZ 1196814 - CWD must == context with -f option
            os.chdir(dockerfile_dir_path)
        subargs = docker_build_options + ["-t", image_name,
                                          dockerfile_dir_path]
        dockercmd = DockerCmd(self, 'build', subargs)
        # Pass as keywords allows ignoring parameter order
        return [self.BuildDef(image_name=image_name,
                              dockercmd=dockercmd,
                              use_config_repo=use_config_repo,
                              dockerfile_dir_path=dockerfile_dir_path,
                              minus_eff=minus_eff,
                              base_repo_fqin=base_repo_fqin,
                              postproc_cmd_csv=postproc_cmd_csv)]

    def initialize(self):
        super(BuildSubSubtest, self).initialize()
        self.sub_stuff['builds'] = []
        # Side-effect: docker pulls the base-image
        self.sub_stuff['builds'] += self.make_builds(self.config)

    def run_once(self):
        super(BuildSubSubtest, self).run_once()
        for build_def in self.sub_stuff['builds']:
            build_def.dockercmd.execute()

    def postprocess(self):
        try:
            super(BuildSubSubtest, self).postprocess()
        except:
            for build_def in self.sub_stuff['builds']:
                build_def.dockercmd.verbose = True
                self.logdebug(str(build_def.dockercmd))
            raise


class local_path(BuildSubSubtest):
    pass


class https_file(BuildSubSubtest):
    pass


class git_path(BuildSubSubtest):
    pass


class bad(BuildSubSubtest):  # negative test
    pass


class bad_quiet(BuildSubSubtest):  # negative test
    pass


class bad_force_rm(BuildSubSubtest):  # negative test
    pass


class rm_false(BuildSubSubtest):
    pass


class jsonvol(BuildSubSubtest):
    pass


class dockerignore(BuildSubSubtest):
    pass
