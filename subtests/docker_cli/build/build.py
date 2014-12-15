r"""
Summary
----------

Tests the ``docker build`` command operation with a set of options
and pre-defined build-content.  Sub-subtests ending in ``path``
test from a build context directory containing a Dockerfile.  The
entire contents will be sent to the docker daemon.  Sub-subtests
ending in ``file`` test from only a specific Dockerfile.  In this
case, the build context is sub-subtest dependent

Operational Summary
--------------------

#. Copy source files
#. Verify timeout isn't too short
#. Start build
#. Check build exit code, make sure image exists
#. Optionally remove built image

Prerequisites
----------------

*  Tarballs bundled with the subtest
*  Statically linked 'busybox' executable available on path or over HTTP
"""

import os.path
import re
import shutil
from urllib2 import urlopen
from dockertest import subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.output import OutputGood
from dockertest.xceptions import DockerTestNAError


RE_IMAGES = re.compile(r' ---> (\w{64}|\w{12})')
RE_CONTAINERS = re.compile(r' ---> Running in (\w{64}|\w{12})')


class build(subtest.SubSubtestCaller):

    def setup(self):
        super(build, self).setup()
        # Must exist w/in directory holding Dockerfile
        # Use local if possible
        if os.path.exists('/usr/sbin/busybox'):
            shutil.copy('/usr/sbin/busybox', self.srcdir + '/busybox')
        else:
            urlstr = self.config.get('busybox_url', None)
            if urlstr is None:
                raise DockerTestNAError("Missing parameter \"busybox_url\" in"
                                        " config.")
            urlstr = urlstr.strip()
            self.logdebug("Downloading busybox from %s", urlstr)
            resp = urlopen(urlstr, timeout=30)
            data = resp.read()
            busybox = os.open(os.path.join(self.srcdir, 'busybox'),
                              os.O_WRONLY | os.O_CREAT, 0755)
            os.write(busybox, data)
            os.close(busybox)

        for filename in self.config['source_dirs'].split(','):
            # bindir is location of this module
            src = os.path.join(self.bindir, filename)
            # srcdir is recreated if doesn't exist or if test version changes
            dst = os.path.join(self.srcdir, filename)
            shutil.copytree(src, dst)
            # copy the busybox
            shutil.copy(os.path.join(self.srcdir, 'busybox'),
                        os.path.join(dst, 'busybox'))


class build_base(subtest.SubSubtest):

    def dockerfile_dir_path(self, dir_path):
        if dir_path[0] == '/':
            srcdir = self.parent_subtest.srcdir
            dir_path = srcdir + dir_path
        return dir_path

    @classmethod
    def dockerfile_token_value_finder(cls, dockerfile, token):
        re_token = re.compile(r'%s\s+.*' % token)
        re_token_value = re.compile(r'\s+.*')
        re_token_comment = re.compile(r'^\#')
        if re_token_comment.findall(dockerfile):
            return ''
        else:
            token_with_value = re_token.findall(dockerfile)
            token_value = re_token_value.findall(''.join(token_with_value))
            return ''.join(token_value).strip(' ')

    def dockerfile_repo_replace(self, path, repo):
        dockerfile_new_data = ''
        dockerfile_old = open(path, 'r')
        try:
            dockerfile_line = dockerfile_old.readlines()
        finally:
            dockerfile_old.close()
        for token_line in dockerfile_line:
            repo_old = self.dockerfile_token_value_finder(token_line, "FROM")
            if repo_old:
                token_line = token_line.replace(repo_old, repo)
            dockerfile_new_data += token_line
        dockerfile_new = open(path, 'w')
        try:
            dockerfile_new.write(dockerfile_new_data)
        finally:
            dockerfile_new.close()

    def _initialize_repo(self, config_repo, file_path, repo_name):
        if config_repo:
            self.dockerfile_repo_replace(file_path, repo_name)
        else:
            tarball = open(os.path.join(self.parent_subtest.bindir,
                                        'empty_base_image.tar'), 'rb')
            dkrcmd = DockerCmd(self, 'import', ["-", "empty_base_image"])
            mustpass(dkrcmd.execute(stdin=tarball))

    def initialize(self):
        super(build_base, self).initialize()
        # Get the latest container (remove all newly created in cleanup
        self.sub_stuff['dc'] = dcont = DockerContainers(self)
        self.sub_stuff['existing_containers'] = dcont.list_container_ids()
        self.sub_stuff['di'] = dimg = DockerImages(self)
        self.sub_stuff['existing_images'] = dimg.list_imgs_ids()
        img_name = dimg.get_unique_name()
        # Build definition:
        # build['image_name'] - name
        # build['dockerfile_dir_path'] - path to docker file directory
        # build['result'] - results of docker build ...
        # build['intermediary_containers'] - Please set to true when --rm=False
        # build['use_config_repo'] - Whether use repo 'docker_repo_name'
        # build['dockerfile_path'] - path to Dockerfile
        # build['base_repo_fqin'] - repo name in 'docker_rpo_name'
        build_def = {}
        self.sub_stuff['builds'] = [build_def]
        build_def['image_name'] = img_name
        if 'dockerfile_use_config_repo' not in self.config:
            use_config_repo = 'net_dockerfile'
        else:
            use_config_repo = self.config.get('dockerfile_use_config_repo')
        build_def['use_config_repo'] = use_config_repo
        dir_path = self.config.get('dockerfile_dir_path')
        if not dir_path:
            raise DockerTestNAError(
                "config['dockerfile_dir_path'] not provided")
        build_def['dockerfile_dir_path'] = self.dockerfile_dir_path(dir_path)
        if build_def['use_config_repo'] != 'net_dockerfile':
            file_path = build_def['dockerfile_dir_path'] + '/' + 'Dockerfile'
            if not os.path.isfile(file_path):
                raise DockerTestNAError("Dockerfile does not exist")
            build_def['dockerfile_path'] = file_path
        else:
            build_def['dockerfile_path'] = ''
        im_cnt = self.config.get('docker_build_intermediary_containers')
        build_def['intermediary_containers'] = im_cnt
        build_def['build_fail_msg'] = self.config.get('docker_build_fail_msg')
        build_def['stdout'] = self.config.get('docker_build_stdout')
        build_def['no_stdout'] = self.config.get('docker_build_no_stdout')
        full_repo = DockerImage.full_name_from_defaults(self.config)
        build_def['full_repo'] = full_repo
        if build_def['dockerfile_path']:
            self._initialize_repo(build_def['use_config_repo'],
                                  build_def['dockerfile_path'],
                                  build_def['full_repo'])

    def run_once(self):
        super(build_base, self).run_once()
        # Run single build
        self._build_container(self.sub_stuff['builds'][0],
                              [self.config['docker_build_options']])

    def _build_container(self, build_def, subargs):
        """
        Build container according to the `build_def` dictionary.
        """
        subargs += ["-t", build_def['image_name'],
                    build_def['dockerfile_dir_path']]
        dkrcmd = DockerCmd(self, 'build', subargs,
                           self.config['build_timeout_seconds'],
                           verbose=True)
        build_def['result'] = dkrcmd.execute()

    def _postprocess_exit_status(self, build_def):
        """
        Check the exit status and eventually the build_fail_msg.
        """
        if build_def.get('build_fail_msg'):
            self.failif(build_def['result'].exit_status == 0, "Build returned "
                        "0 even thought it was expected to fail: %s"
                        % build_def['result'])
            out = "%s\n%s" % (build_def['result'].stdout,
                              build_def['result'].stderr)
            exp = build_def.get('build_fail_msg')
            self.failif(exp not in out, "Expected failure message '%s' not "
                        "found in the build output:\n%s"
                        % (exp, build_def['result']))
        else:
            OutputGood(build_def['result'])
            self.failif(build_def['result'].exit_status != 0, "Non-zero build "
                        "exit status: %s" % build_def['result'])
        self.logdebug("%s:\tExit status\tOK", build_def['image_name'])

    def _postprocess_created_images(self, build_def):
        """
        Check that all expected images were created
        """
        dkrimgs = self.sub_stuff['di']
        # Named image
        if not build_def.get('build_fail_msg'):     # Only when build passed
            imgs = dkrimgs.list_imgs_with_full_name(build_def['image_name'])
            self.failif(len(imgs) < 1, "Test image '%s' not found in images\n"
                        "%s" % (build_def['image_name'],
                                dkrimgs.list_imgs_full_name()))
        # Intermediary images
        dkrimgs.images_args += " -a"    # list all
        images = dkrimgs.list_imgs()
        dkrimgs.images_args = dkrimgs.images_args[:-3]
        created_images = RE_IMAGES.findall(build_def['result'].stdout)
        for img_id in created_images:
            imgs = [_.long_id for _ in images if _.cmp_id(img_id)]
            self.failif(len(imgs) != 1, "Intermediary image '%s' not present "
                        "once in images\n%s" % (img_id, images))
        self.logdebug("%s:\tMain image + %s intermediary images\tOK",
                      build_def['image_name'], len(created_images))

    def _postprocess_created_containers(self, build_def):
        """
        Check that used containers were (not) removed
        """
        # Intermediary containers
        containers = self.sub_stuff['dc'].list_containers()
        created_containers = RE_CONTAINERS.findall(build_def['result'].stdout)
        if build_def.get('intermediary_containers') == 'LAST':
            # Only last one should be present (use this when build fails)
            for cont in created_containers[:-1]:     # All but one exist
                conts = [_.long_id for _ in containers if _.cmp_id(cont)]
                self.failif(len(conts) != 0, "Intermediary container '%s' is "
                            "present although it should been removed by build"
                            "\n%s" % (cont, containers))
            # Last one should not
            conts = [_.long_id for _ in containers
                     if _.cmp_id(created_containers[-1])]
            self.failif(len(conts) != 1, "Intermediary container '%s' not "
                        "present once in containers\n%s"
                        % (created_containers[-1], containers))
        elif build_def.get('intermediary_containers'):    # should be preserved
            for cont in created_containers:
                conts = [_.long_id for _ in containers if _.cmp_id(cont)]
                self.failif(len(conts) != 1, "Intermediary container '%s' not "
                            "present once in containers\n%s" % (cont,
                                                                containers))
        else:   # should not be present
            for cont in created_containers:
                conts = [_.long_id for _ in containers if _.cmp_id(cont)]
                self.failif(len(conts) != 0, "Intermediary container '%s' is "
                            "present although it should been removed by build"
                            "\n%s" % (cont, containers))
        self.logdebug("%s:\t%s intermediary containers\tOK",
                      build_def['image_name'], len(created_containers))

    def _postprocess_output(self, build_def):
        """
        Checks the presence of messages in the output
        """
        result = build_def['result']
        exp = build_def.get('stdout')
        self.failif(exp and not re.search(exp, result.stdout, re.M), "Expected"
                    " message '%s' not found in build stdout:\n%s"
                    % (exp, result))
        exp = build_def.get('no_stdout')
        self.failif(exp and re.search(exp, result.stdout, re.M), "Forbidden "
                    "message '%s' was found in build stdout:\n%s"
                    % (exp, result))
        self.logdebug("%s:\tOutput messages\tOK", build_def['image_name'])

    def _postprocess_no_containers(self):
        """
        Check that during test run expected number of containers were created
        """
        containers_pre = self.sub_stuff['existing_containers']
        containers_post = self.sub_stuff['dc'].list_container_ids()
        _all = self.config.get('dockerfile_all_containers', 0)
        _new = self.config.get('dockerfile_new_containers', 0)
        diff = len(containers_post) - len(containers_pre)
        if _new != 0:
            # No new containers
            self.failif(diff == 0, "No new containers created in build "
                        "(rm=False).")
        # Too many new containers
        if _all != _new:
            self.failif(diff == _all, "Number of containers before and after "
                        "second build (--rm=False) is exactly of %s higher, "
                        "cache was probably not used and containers for all "
                        "(even cached) steps were created." % _all)
        # Other count
        self.failif(diff != _new, "Number of containers before and after "
                    "second build (--rm=False) is not of %s containers higher."
                    " That's really weird...).\nBefore: %s\nAfter: %s"
                    % (_new, containers_pre, containers_post))
        self.logdebug("ALL:\tNumber of created containers\tOK")

    def _postprocess_result(self, build_def):
        """
        Go through results and check all containers were created
        """
        self._postprocess_exit_status(build_def)
        self._postprocess_created_images(build_def)
        self._postprocess_created_containers(build_def)
        self._postprocess_output(build_def)

    def postprocess(self):
        super(build_base, self).postprocess()
        for build_def in self.sub_stuff['builds']:
            self._postprocess_result(build_def)
        self._postprocess_no_containers()

    def cleanup(self):
        super(build_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['remove_after_test']:
            # Remove all previously non-existing containers
            for cid in self.sub_stuff['dc'].list_container_ids():
                if cid in self.sub_stuff['existing_containers']:
                    continue    # don't remove previously existing ones
                dcmd = DockerCmd(self, 'rm', ['--force', '--volumes', cid],
                                 verbose=False)
                dcmd.execute()
            dimg = self.sub_stuff['di']
            # Remove all previously non-existing images
            for img in dimg.list_imgs_ids():
                if img in self.sub_stuff['existing_images']:
                    continue
                dimg.remove_image_by_id(img)


class local_path(build_base):
    pass


class https_file(build_base):
    pass


class git_path(build_base):
    pass


class bad(build_base):
    pass


class bad_quiet(build_base):
    pass


class bad_force_rm(build_base):
    pass
