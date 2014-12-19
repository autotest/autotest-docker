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

*  Tarballs bundled with the subtest
*  Statically linked 'busybox' executable available on path or over HTTP
*  Behavior in Dockerfiles match expected behavior of sub-subtest & config.
"""

import os.path
import re
import shutil
from collections import namedtuple
from urllib2 import urlopen
from dockertest import subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.output import mustfail
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.output import OutputGood
from dockertest.config import get_as_list

# Generate named tuple class to hold fixed build parameters
BuildDef = namedtuple('BuildDef',
                      ['image_name',               # Name of image to build
                       'dockercmd',                # Execution state
                       'intermediate_containers',  # True/False/LAST
                       'additional_containers',    # No. present after build
                       'use_config_repo',          # True/False
                       'dockerfile_dir_path',      # full path / url / git repo
                       'base_repo_fqin',           # Substitute for FROM
                       'positive_build_regex',     # Regex positive test
                       'negative_build_regex'])    # Regex negative test

RE_IMAGES = re.compile(r'\s*-+>\s*(\w{64}|\w{12})')
RE_CONTAINERS = re.compile(r's*-+>\s*Running in\s*(\w{64}|\w{12})')


class build(subtest.SubSubtestCaller):

    def setup(self):
        super(build, self).setup()
        # Must exist w/in directory holding Dockerfile
        # Use local if possible
        if os.path.exists('/usr/sbin/busybox'):
            shutil.copy('/usr/sbin/busybox',
                        os.path.join(self.srcdir, 'busybox'))
        else:
            urlstr = self.config['busybox_url']
            urlstr = urlstr.strip()
            self.logdebug("Downloading busybox from %s", urlstr)
            resp = urlopen(urlstr, timeout=30)
            data = resp.read()
            busybox = os.open(os.path.join(self.srcdir, 'busybox'),
                              os.O_WRONLY | os.O_CREAT, 0755)
            os.write(busybox, data)
            os.close(busybox)

        source_dirs = self.config['source_dirs']
        for dir_path in get_as_list(source_dirs):
            # bindir is location of this module
            src = os.path.join(self.bindir, dir_path)
            # srcdir is recreated if doesn't exist or if test version changes
            dst = os.path.join(self.srcdir, dir_path)
            shutil.copytree(src, dst)
            # copy busybox
            shutil.copy(os.path.join(self.srcdir, 'busybox'),
                        os.path.join(dst, 'busybox'))


class build_base(subtest.SubSubtest):

    def dockerfile_dir_path(self, dir_path):
        if not isinstance(dir_path, basestring) or dir_path is None:
            return dir_path
        if dir_path[0] == '/':
            srcdir = self.parent_subtest.srcdir
            abs_dir_path = os.path.join(srcdir, dir_path)
            if os.path.isdir(abs_dir_path):
                return abs_dir_path
            # else, fall through, return un-modified dir_path
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

    def initialize_utils(self):
        # Get the latest container (remove all newly created in cleanup
        self.sub_stuff['dc'] = dcont = DockerContainers(self)
        self.sub_stuff['existing_containers'] = dcont.list_container_ids()
        self.sub_stuff['di'] = dimg = DockerImages(self)
        self.sub_stuff['existing_images'] = dimg.list_imgs_ids()

    def make_builds(self, source):
        dimg = self.sub_stuff['di']
        image_name = dimg.get_unique_name()
        intermediate_containers = source['intermediate_containers']
        additional_containers = source['additional_containers']
        positive_build_regex = source['positive_build_regex'].strip()
        negative_build_regex = source['negative_build_regex'].strip()
        base_repo_fqin = DockerImage.full_name_from_defaults(source)
        use_config_repo = source['use_config_repo']
        dockerfile_dir_path = source['dockerfile_dir_path'].strip()
        # Only replace w/ abs-path if dockerfile_dir_path starts with '/'
        # and if the abs-path points to an existing directory
        dockerfile_dir_path = dockerfile_dir_path(dockerfile_dir_path)
        if use_config_repo:  # Indicates NOT a url / git repo
            # Form full path including "Dockerfile"
            full_dockerfile_path = os.path.join(dockerfile_dir_path,
                                                'Dockerfile')
            self.dockerfile_repo_replace(full_dockerfile_path,
                                         base_repo_fqin)
            del full_dockerfile_path  # no longer needed
        # else:  dockerfile_dir_path is a url or git repo, read-only
        docker_build_options = source['docker_build_options'].strip()
        subargs = get_as_list(docker_build_options) + ["-t", image_name,
                                                       dockerfile_dir_path]
        dockercmd = DockerCmd(self, 'build', subargs, verbose=True)
        # Pass as keywords allows ignoring parameter order
        return [BuildDef(image_name=image_name,
                         dockercmd=dockercmd,
                         intermediate_containers=intermediate_containers,
                         additional_containers=additional_containers,
                         use_config_repo=use_config_repo,
                         dockerfile_dir_path=dockerfile_dir_path,
                         base_repo_fqin=base_repo_fqin,
                         positive_build_regex=positive_build_regex,
                         negative_build_regex=negative_build_regex)]

    def initialize(self):
        super(build_base, self).initialize()
        self.initialize_utils()
        self.sub_stuff['builds'] = []
        self.sub_stuff['builds'] += self.make_builds(self.config)

    def run_once(self):
        super(build_base, self).run_once()
        for build_def in self.sub_stuff['builds']:
            build_def.dockercmd.execute()

    def postprocess_positive(self, build_def, check_stderr=False):
        # Verify exit status
        mustpass(build_def.dockercmd.cmdresult)
        OutputGood(build_def.dockercmd.cmdresult)
        if check_stderr:
            output = build_def.dockercmd.stderr
        else:
            output = build_def.dockercmd.stdout
        # Fail if does not match positive regex
        if build_def.positive_build_regex != '':
            positive_regex = re.compile(build_def.positive_build_regex)
            mobj = positive_regex.search(output)
            self.failif(mobj is None,
                        "Positive message not found in output")
        # Fail if match negative regex
        if build_def.negative_build_regex != '':
            negative_regex = re.compile(build_def.negative_build_regex)
            mobj = negative_regex.search(output)
            self.failif(mobj is not None,
                        "Negative message found in output")
        self.loginfo("Positive test checks pass")

    def postprocess_negative(self, build_def, check_stderr=False):
        # Verify exit status
        mustfail(build_def.dockercmd.cmdrsult)
        # Only check for panic or usage message
        OutputGood(build_def.dockercmd.cmdresult, skip='error_check')
        if check_stderr:
            output = build_def.dockercmd.stderr
        else:
            output = build_def.dockercmd.stdout
        # Fail if match positive regex
        if build_def.positive_build_regex != '':
            positive_regex = re.compile(build_def.positive_build_regex)
            mobj = positive_regex.search(output)
            # reverse of postprocess_positive()
            self.failif(mobj is not None,
                        "Positive message found in output")
        # Fail if does not match negative regex
        if build_def.negative_build_regex != '':
            negative_regex = re.compile(build_def.negative_build_regex)
            mobj = negative_regex.search(output)
            # reverse of postprocess_positive()
            self.failif(mobj is None,
                        "Negative message not found in output")
        self.loginfo("Negative test checks pass")

    def postprocess_created_images(self, build_def):
        dkrimgs = self.sub_stuff['di']
        dkrimgs.images_args += " --all"    # list all
        images = dkrimgs.list_imgs()
        dkrimgs.images_args = DockerImages.images_args

        img_names = [di.full_name for di in images]
        imf_ids = [di.short_id for di in images]
        self.failif(build_def.image_name not in img_names,
                    "Test image '%s' not found after build"
                    % build_def.image_name)

        stdout = build_def.dockercmd.stdout
        created_ids = [mobj.group(1)
                       for mobj in RE_IMAGES.finditer(stdout)
                       if mobj is not None]
        for created_id in created_ids:
            self.failif(created_id not in imf_ids,
                        "Intermediate image %s not found after build"
                        % created_id)

    def postprocess_intermediate_last(self, containers, created_containers):
        # Only last one should be present
        # e.g. build fails w/ --rm=true
        for cid in created_containers[:-1]:  # All except last one
            self.failif(cid in containers,
                        "Found unexpected intermediate container %s "
                        "after build" % cid)
        self.failif(created_containers[-1] not in containers,
                    "Couldn't find expected final container %s "
                    "left after failed build" % created_containers[-1])

    def postprocess_intermediate_true(self, containers, created_containers):
        # All expected intermediate containers should be present
        # e.g. build succeeds with --rm=false
        for cid in created_containers:
            self.failif(cid not in containers,
                        "Couldn't find expected intermediate container %s "
                        "after build" % cid)

    def postprocess_intermediate_false(self, containers, created_containers):
        # No intermediate container should be present
        # e.g. build fails with --force-rm
        for cid in created_containers:
            self.failif(cid in containers,
                        "Found unexpected intermediate container %s "
                        "after build" % cid)

    def postprocess_created_containers(self, build_def):
        dcont = self.sub_stuff['dc']
        # Only short ID's are printed, only match short ids
        containers = [cid[0:12] for cid in dcont.list_container_ids()]

        stdout = build_def.dockercmd.stdout
        created_containers = [mobj.group(1)
                              for mobj in RE_CONTAINERS.search(stdout)
                              if mobj is not None]

        if build_def.intermediate_containers == 'LAST':
            self.postprocess_intermediate_last(containers, created_containers)
        elif build_def.intermediate_containers is True:
            self.postprocess_intermediate_true(containers, created_containers)
        elif build_def.intermediate_containers is False:
            self.postprocess_intermediate_false(containers, created_containers)
        else:
            self.logdebug("Not checking intermediate containers")

    def postprocess_container_count(self, build_def):
        expected = int(build_def.additional_containers)
        containers_pre = self.sub_stuff['existing_containers']
        containers_post = self.sub_stuff['dc'].list_container_ids()
        diff = len(containers_post) - len(containers_pre)
        self.failif(diff != expected,
                    "Expected %d containers, found %d"
                    % (expected, diff))

    def postprocess_result(self, build_def):
        self.postprocess_positive(build_def)
        self.postprocess_created_images(build_def)
        self.postprocess_created_containers(build_def)
        self.postprocess_container_count(build_def)

    def postprocess(self):
        super(build_base, self).postprocess()
        for build_def in self.sub_stuff['builds']:
            self.postprocess_result(build_def)
        self.postprocess_no_containers()

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


class bad(build_base):  # negative test

    def postprocess_result(self, build_def):
        self.postprocess_negative(build_def)
        self.postprocess_created_images(build_def)
        self.postprocess_created_containers(build_def)
        self.postprocess_container_count(build_def)


class bad_quiet(bad):  # negative test
    pass


class bad_force_rm(bad):  # negative test
    pass


class rm_false(build_base):
    pass


class cache(build_base):

    def make_builds(self, source):
        first = source.deepcopy()
        second = source.deepcopy()
        # Just remote all key2's to keep tidy
        for key in first.keys():  # dict is being modified
            if key.endswith('2'):
                del first[key]
        # Move key2 values, remove key2 to keep tidy
        for key in second.keys():  # move '2' key valus
            if key.endswith('2'):
                second[key[:-1]] = second[key]  # copy value
                del second[key]  # remove 2 key
        super_make_builds = super(cache, self).make_builds
        return super_make_builds(first) + super_make_builds(second)
