from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from run import run_base


class run_remote_tag(run_base):

    def init_image(self):
        fqin = self.config["remote_image_fqin"]
        self.sub_stuff['fqin'] = fqin
        dimg = self.sub_stuff["img"]
        # image name may map to multiple ids
        dimgs = dimg.list_imgs_with_full_name(fqin)
        for dimgobj in dimgs:
            # In case multiple tags are pulled down
            self.sub_stuff["images"].append(dimgobj.full_name)
            dimg.remove_image_by_image_obj(dimgobj)

    def postprocess(self):
        super(run_remote_tag, self).postprocess()  # Prints out basic info
        # Fail test if image removal fails
        fqin = self.config["remote_image_fqin"]
        mustpass(DockerCmd(self, 'rmi', ['--force', fqin]).execute())
