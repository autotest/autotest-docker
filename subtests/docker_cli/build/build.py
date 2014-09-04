"""
Test run of docker build command

1. Copy source files + static busybox to srcdir if necessary
2. Verify timeout isn't too short
3. Start build in srcdir
4. Check build exit code, make sure image exists
5. Optionally remove built image
"""

import os.path
import re
import shutil
from urllib2 import urlopen

from dockertest import subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd, NoFailDockerCmd
from dockertest.images import DockerImages
from dockertest.output import OutputGood
from dockertest.xceptions import DockerTestNAError


RE_IMAGES = re.compile(r' ---> (\w{64}|\w{12})')
RE_CONTAINERS = re.compile(r' ---> Running in (\w{64}|\w{12})')


class build(subtest.SubSubtestCaller):

    """ Subtest caller """

    def setup(self):
        super(build, self).setup()
        # Must exist w/in directory holding Dockerfile
        urlstr = self.config['busybox_url'].strip()
        self.logdebug("Downloading busybox from %s", urlstr)
        resp = urlopen(urlstr, timeout=30)
        data = resp.read()
        busybox = os.open(os.path.join(self.srcdir, 'busybox'),
                          os.O_WRONLY | os.O_CREAT, 0755)
        os.write(busybox, data)
        os.close(busybox)
        #shutil.copy('/usr/sbin/busybox', self.srcdir + '/busybox')

        for filename in self.config['source_dirs'].split(','):
            # bindir is location of this module
            src = os.path.join(self.bindir, filename)
            # srcdir is recreated if doesn't exist or if test version changes
            dst = os.path.join(self.srcdir, filename)
            shutil.copytree(src, dst)
            # copy the busybox
            shutil.copy(os.path.join(self.srcdir, 'busybox'),
                        os.path.join(dst, 'busybox'))

    def initialize(self):
        super(build, self).initialize()
        # Most tests use 'empty_base_image'. Add it only here
        tarball = open(os.path.join(self.bindir, 'empty_base_image.tar'), 'rb')
        dkrcmd = NoFailDockerCmd(self, 'import', ["-", "empty_base_image"])
        dkrcmd.execute(stdin=tarball)

    def cleanup(self):
        super(build, self).cleanup()
        DockerImages(self).remove_image_by_full_name("empty_base_image")


class build_base(subtest.SubSubtest):

    """
    Base of build test
    1. Import empty_base_image (widely used in this test)
    2. Run docker build ... $dockerfile_path (by default self.srcdir)
    3. Verify the image was built successfully
    """
    def dockerfile_path(self, path):
        if path[0] == '/':
            srcdir = self.parent_subtest.srcdir
            path = srcdir + path
        return path

    def initialize(self):
        super(build_base, self).initialize()
        # Get the latest container (remove all newly created in cleanup
        self.sub_stuff['dc'] = dcont = DockerContainers(self)
        self.sub_stuff['existing_containers'] = dcont.list_container_ids()
        self.sub_stuff['di'] = dimg = DockerImages(self)
        self.sub_stuff['existing_images'] = dimg.list_imgs_ids()
        img_name = dimg.get_unique_name(self.config['image_name_prefix'],
                                        self.config['image_name_postfix'])
        # Build definition:
        # build['image_name'] - name
        # build['dockerfile_path'] - path to docker file
        # build['result'] - results of docker build ...
        # build['intermediary_containers'] - Please set to true when --rm=False
        build_def = {}
        self.sub_stuff['builds'] = [build_def]
        build_def['image_name'] = img_name
        path = self.config.get('dockerfile_path')
        if not path:
            raise DockerTestNAError("config['dockerfile_path'] not provided")
        build_def['dockerfile_path'] = self.dockerfile_path(path)

    def run_once(self):
        super(build_base, self).run_once()
        # Run single build
        self._build_container(self.sub_stuff['builds'][0],
                              [self.config['docker_build_options']])

    def _build_container(self, build_def, subargs):
        subargs += ["-t", build_def['image_name'],
                    build_def['dockerfile_path']]
        dkrcmd = DockerCmd(self, 'build', subargs,
                           self.config['build_timeout_seconds'],
                           verbose=True)
        build_def['result'] = dkrcmd.execute()

    def postprocess(self):
        super(build_base, self).postprocess()
        for build_def in self.sub_stuff['builds']:
            self.postprocess_result(build_def)

    def postprocess_result(self, build_def):
        """
        Go through results and check all containers were created
        """
        # Exit status
        OutputGood(build_def['result'])
        self.failif(build_def['result'].exit_status != 0, "Non-zero build "
                    "exit status: %s" % build_def['result'])
        # Named image
        dkrimgs = self.sub_stuff['di']
        imgs = dkrimgs.list_imgs_with_full_name(build_def['image_name'])
        self.failif(len(imgs) < 1, "Test image '%s' not found in images\n%s"
                    % (build_def['image_name'], dkrimgs.list_imgs_full_name()))
        # Intermediary images
        dkrimgs.images_args += " -a"    # list all
        images = dkrimgs.list_imgs()
        dkrimgs.images_args = dkrimgs.images_args[:-3]
        for img_id in RE_IMAGES.findall(build_def['result'].stdout):
            imgs = [_.long_id for _ in images if _.cmp_id(img_id)]
            self.failif(len(imgs) != 1, "Intermediary image '%s' not present "
                        "once in images\n%s" % (img_id, images))
        # Intermediary containers
        containers = self.sub_stuff['dc'].list_containers()
        if build_def.get('intermediary_containers'):    # should be preserved
            for cont in RE_CONTAINERS.findall(build_def['result'].stdout):
                conts = [_.long_id for _ in containers if _.cmp_id(cont)]
                self.failif(len(conts) != 1, "Intermediary container '%s' not "
                            "present once in containers\n%s" % (cont,
                                                                containers))
        else:   # should not be present
            for cont in RE_CONTAINERS.findall(build_def['result'].stdout):
                conts = [_.long_id for _ in containers if _.cmp_id(cont)]
                self.failif(len(conts) != 0, "Intermediary container '%s' is "
                            "present although it should been removed by build"
                            "\n%s" % (cont, containers))

    def cleanup(self):
        super(build_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['try_remove_after_test']:
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

    """
    Path to a local directory within the Dockerfile and other files are present
    """
    pass


class https_file(build_base):

    """ https path to a Dockerfile """
    pass


class git_path(build_base):

    """ path to a git reporistory which contains Dokerfile and othe files """
    pass
