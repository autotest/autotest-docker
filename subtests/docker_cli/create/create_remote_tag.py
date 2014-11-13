import os.path
from autotest.client.shared import error
from dockertest.output import mustpass
from dockertest.dockercmd import DockerCmd
from dockertest.config import get_as_list
from dockertest.xceptions import DockerTestFail
from autotest.client import utils
from create import create_base


class create_remote_tag(create_base):

    def init_subargs_imgcmd(self):
        if self.config["remote_image_fqin"] == "":
            raise error.TestNAError("Unable to prepare env for test:"
                                    "create_remote_tag/remote_image_fqin has "
                                    "to be set to functional repo address.")
        self.sub_stuff['subargs'].append(self.config["remote_image_fqin"])
        self.sub_stuff['subargs'] += get_as_list(self.config['bash_cmd'])
        self.sub_stuff['subargs'].append(self.config['cmd'])

    def long_id_in_images(self, long_id):
        di = self.sub_stuff['img']
        long_ids = [img.long_id
                    for img in di.list_imgs_with_image_id(long_id)]
        # Retrn True if long_ids is empty
        return not bool(len(long_ids))

    def init_save_images(self):
        # If images w/ same id as remote image already exist, save then remove
        di = self.sub_stuff['img']
        imgs = di.list_imgs_with_full_name(self.config["remote_image_fqin"])
        if imgs:
            long_id = imgs[0].long_id
            existing_images = di.list_imgs_with_image_id(long_id)
            self.sub_stuff['saved_images'] = os.path.join(self.tmpdir,
                                                          str(long_id))
            subargs = ['--output', self.sub_stuff['saved_images']]
            for img in existing_images:
                self.loginfo("Going to save image %s" % img.full_name)
                subargs.append(img.full_name)
            self.loginfo("Saving images...")
            mustpass((self, 'save', subargs).execute())
            self.loginfo("Removing images...")
            subargs = ['--force']
            subargs += [img.full_name for img in existing_images]
            mustpass(DockerCmd(self, 'rmi', subargs, verbose=True).execute())
            # Wait for images to actually go away
            _fn = lambda: self.long_id_in_images(long_id)
            gone = utils.wait_for(_fn, 60, step=1,
                                  text="Waiting for image removal")
            self.logdebug("Current images: %s", di.list_imgs())
            if not gone:
                raise DockerTestFail("Timeout waiting for removal of %s"
                                     % long_id)

    def initialize(self):
        self.sub_stuff['saved_images'] = None
        super(create_remote_tag, self).initialize()
        # Record filename to tar archive holding copy of all images
        # related to remote_image_fqin before removing them.
        self.init_save_images()

    def cleanup(self):
        # Be certain any containers are removed
        super(create_remote_tag, self).cleanup()
        # if remote image downloaded, remove it
        DockerCmd(self, 'rmi',
                  [self.config["remote_image_fqin"]], verbose=False).execute()
        # recover original images that had same id
        si = self.sub_stuff['saved_images']
        if si is not None:
            self.loginfo("Recovering saved images...")
            DockerCmd(self, 'load', ['--input', si], timeout=120).execute()
