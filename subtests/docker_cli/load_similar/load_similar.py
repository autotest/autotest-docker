"""
Summary
-------

Verify that when loading container with the same ID but different content
it actually overwrites the container.

Operation Summary
-----------------

#.  Prepare container with new file
#.  Commit the container and save it
#.  Extract the new layer and modify the new file
#.  Load the original and verify new file content (original)
#.  Load the modified and verify new file content (modified)
"""
from dockertest import subtest
from dockertest.dockercmd import NoFailDockerCmd, DockerCmd
from dockertest.images import DockerImages, DockerImage
from dockertest.containers import DockerContainers
import os
from autotest.client import utils


class load_similar(subtest.Subtest):

    """
    Test body
    stuff['container'] - name of container used in setup
    stuff['img'] - image name used in setup
    stuff['img_id'] - id of the created image
    """

    def setup(self):
        super(load_similar, self).setup()
        # Prepare directories
        original_dir = os.path.join(self.srcdir, "original")
        corrupted_dir = os.path.join(self.srcdir, "corrupted")
        os.mkdir(original_dir)
        os.mkdir(corrupted_dir)
        # Create container with /testfile
        name = DockerContainers(self).get_unique_name()
        self.stuff['container'] = name
        fin = DockerImage.full_name_from_defaults(self.config)
        cmd = 'sh -c "echo 1234567890 > /testfile"'
        NoFailDockerCmd(self, "run", ["--name %s" % name, fin, cmd],
                        verbose=False).execute()
        # Commit the image and persistently store it's id
        self.stuff['img'] = DockerImages(self).get_unique_name()
        img_id = NoFailDockerCmd(self, "commit", [name, self.stuff['img']],
                                 verbose=False).execute().stdout.strip()
        self.stuff['img_id'] = img_id
        utils.run("echo -n %s > %s/img_id" % (img_id, self.srcdir))
        NoFailDockerCmd(self, "save",
                        [self.stuff['img'], "> %s/test.tar" % original_dir],
                        verbose=False).execute()
        # Extract to corrupted dir
        utils.run("tar -xf %s/test.tar -C %s" % (original_dir, corrupted_dir))
        os.chdir(os.path.join(corrupted_dir, self.stuff['img_id']))
        # Modify the testfile content
        utils.run("echo 1234567890A > testfile")
        # Pack everything to work with ``docker load``
        utils.run("tar -cf layer.tar testfile")
        os.chdir("..")
        utils.run("tar -cf test.tar *")

    def run_once(self):
        super(load_similar, self).run_once()
        img_id = self.stuff.get('img_id')
        if not img_id:
            img_id = utils.run("cat %s/img_id" % self.srcdir).stdout.strip()
            self.stuff['img_id'] = img_id

        # Check original
        cmd = "cat /testfile"
        original_path = os.path.join(self.srcdir, "original", "test.tar")
        NoFailDockerCmd(self, "load", ["< %s" % original_path],
                        verbose=False).execute()
        original = NoFailDockerCmd(self, "run", ["--rm", img_id, cmd],
                                   verbose=False).execute().stdout.strip()
        self.failif(original != "1234567890", "Content of the original "
                    "image is not 1234567890 (%s)" % original)

        # Check corrupted
        corrupted_path = os.path.join(self.srcdir, "corrupted", "test.tar")
        NoFailDockerCmd(self, "load", ["< %s" % corrupted_path],
                        verbose=False).execute()
        corrupted = NoFailDockerCmd(self, "run", ["--rm", img_id, cmd],
                                    verbose=False).execute().stdout.strip()
        self.failif(corrupted == "1234567890", "Content of the corrupted "
                    "image is not 1234567890A, but still the same value as "
                    "the original image (1234567890)")
        self.failif(corrupted != "1234567890A", "Content of the corrupted "
                    "image is not 1234567890A (%s)" % corrupted)

    def cleanup(self):
        super(load_similar, self).cleanup()
        dimg = DockerImages(self)
        if self.config['remove_after_test']:
            # Remove created/loaded image
            if self.stuff['img_id']:
                dimg.remove_image_by_id(self.stuff['img_id'])
            elif self.stuff['img']:
                dimg.remove_image_by_name(self.stuff['img'])

            # Remove container from setup
            if self.stuff['container']:
                DockerCmd(self, 'rm',
                          ['--force', '--volumes', self.stuff['container']],
                          verbose=False).execute()
