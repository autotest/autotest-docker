"""
Test docker run by executing basic commands inside container and checking the
results.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest.subtest import SubSubtest, SubSubtestCaller
from dockertest.dockercmd import DockerCmd
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.output import OutputGood
from autotest.client.shared import error


class run(SubSubtestCaller):
    config_section = 'docker_cli/run'

    def cleanup(self):
        super(run, self).cleanup()
        # Clean up all containers
        dc = DockerContainers(self)
        for cobj in dc.list_containers():
            self.logwarning("Found leftover container: %s", cobj.container_name)
            try:
                dc.kill_container_by_obj(cobj)
            except ValueError:
                pass  # already dead
            else:
                self.logdebug("Killed container %s, waiting up to %d seconds "
                              "for it to exit", cobj.container_name,
                              dc.timeout)
                dc.wait_by_obj(cobj)
            self.logdebug("Removing container %s", cobj.container_name)
            dc.remove_by_obj(cobj)
        # Clean up all non-default images
        fqin = DockerImage.full_name_from_defaults(self.config)
        di = DockerImages(self)
        def_img_obj = di.list_imgs_with_full_name(fqin)[0]
        for img_obj in di.list_imgs():
            if img_obj.full_name != def_img_obj.full_name:
                self.logwarning("Found leftover image: %s", img_obj)
                di.remove_image_by_image_obj(img_obj)
            else:
                self.logdebug("Not removing default image: %s", def_img_obj)

class run_base(SubSubtest):

    def init_subargs(self):
        self.sub_stuff['subargs'] = self.config['run_options_csv'].split(',')
        fqin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['fqin'] = fqin
        self.sub_stuff['subargs'].append(fqin)
        self.sub_stuff['subargs'] += self.config['bash_cmd'].split(',')
        self.sub_stuff['subargs'].append(self.config['cmd'])

    def initialize(self):
        super(run_base, self).initialize()
        self.init_subargs()
        self.sub_stuff["containers"] = []
        self.sub_stuff["images"] = []
        self.sub_stuff["cont"] = DockerContainers(self.parent_subtest)
        self.sub_stuff["img"] = DockerImages(self.parent_subtest)

    def run_once(self):
        super(run_base, self).run_once()    # Prints out basic info
        dkrcmd = DockerCmd(self.parent_subtest, 'run',
                           self.sub_stuff['subargs'])
        dkrcmd.verbose = True
        self.sub_stuff['cmdresult'] = dkrcmd.execute()

    def postprocess(self):
        super(run_base, self).postprocess()  # Prints out basic info
        if 'cmdresult' in self.sub_stuff:
            # Fail test if bad command or other stdout/stderr problems detected
            OutputGood(self.sub_stuff['cmdresult'])
            expected = self.config['exit_status']
            self.failif(self.sub_stuff['cmdresult'].exit_status != expected,
                        "Exit status non-zero command %s"
                        % self.sub_stuff['cmdresult'])
            self.logdebug(self.sub_stuff['cmdresult'])

    def cleanup(self):
        super(run_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['remove_after_test']:
            for cont in self.sub_stuff.get("containers", []):
                dkrcmd = DockerCmd(self.parent_subtest, "rm",
                                   ['--volumes', '--force', cont])
                cmdresult = dkrcmd.execute()
                msg = (" removed test container: %s" % cont)
                if cmdresult.exit_status == 0:
                    self.logdebug("Successfully" + msg)
                else:
                    self.logwarning("Failed" + msg)
            for image in self.sub_stuff.get("images", []):
                try:
                    di = DockerImages(self.parent_subtest)
                    self.logdebug("Removing image %s", image)
                    di.remove_image_by_full_name(image)
                    self.logdebug("Successfully removed test image: %s",
                                  image)
                except error.CmdError, e:
                    error_text = "tagged in multiple repositories"
                    if not error_text in e.result_obj.stderr:
                        raise


class run_true(run_base):
    pass  # Only change is in configuration


class run_false(run_base):
    pass  # Only change is in configuration
