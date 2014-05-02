"""
Test output of docker save/load command

initialize:
  1) preapare new image
run_once:
  2) save image to disk
  3) remove image from docker
  4) load image from file
postprocess:
  5) Check all results of docker commands.
  6) Check if image again exits in docker.
"""


import os

from autotest.client import utils
from autotest.client.shared import error
from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers
from dockertest.images import DockerImages
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.dockercmd import DockerCmd
from dockertest import subtest

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


class save_load(subtest.SubSubtestCaller):
    config_section = 'docker_cli/save_load'


class save_load_base(SubSubtest):

    def initialize(self):
        super(save_load_base, self).initialize()
        self.sub_stuff['subargs'] = self.config['run_options_csv'].split(',')
        fin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['subargs'].append(fin)
        self.sub_stuff['subargs'].append(self.config['docker_data_prep_cmd'])
        self.sub_stuff["containers"] = []
        self.sub_stuff["images"] = []
        self.sub_stuff["cont"] = DockerContainers(self.parent_subtest)
        self.sub_stuff["img"] = DockerImages(self.parent_subtest)

    def cleanup(self):
        super(save_load_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['remove_after_test']:
            for cont in self.sub_stuff["containers"]:
                dkrcmd = DockerCmd(self.parent_subtest, "rm",
                                   ['--volumes', '--force', cont])
                cmdresult = dkrcmd.execute()
                msg = (" removed test container: %s" % cont)
                if cmdresult.exit_status == 0:
                    self.logdebug("Successfully" + msg)
                else:
                    self.logwarning("Failed" + msg)
            for image in self.sub_stuff["images"]:
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


class simple(save_load_base):

    def initialize(self):
        super(simple, self).initialize()
        rand_name = utils.generate_random_string(8).lower()
        self.sub_stuff["rand_name"] = rand_name
        self.sub_stuff["subargs"].insert(0, "--name=\"%s\"" % rand_name)

        dkrcmd = DockerCmd(self.parent_subtest, 'run',
                           self.sub_stuff['subargs'],
                           verbose=True)

        cmdresult = dkrcmd.execute()
        if cmdresult.exit_status != 0:
            error.TestNAError("Unable to prepare env for test: %s" %
                              (cmdresult))

        c_name = self.sub_stuff["rand_name"]
        self.sub_stuff["images"].append(c_name)
        cid = self.sub_stuff["cont"].list_containers_with_name(c_name)

        self.failif(cid == [],
                    "Unable to search container with name %s: details :%s" %
                   (c_name, cmdresult))

        dkrcmd = DockerCmd(self.parent_subtest, 'commit',
                           [c_name, c_name], verbose=True)
        dkrcmd.verbose = True

        cmdresult = dkrcmd.execute()
        if cmdresult.exit_status != 0:
            error.TestNAError("Unable to prepare env for test: %s" %
                              (cmdresult))
        dkrcmd = DockerCmd(self.parent_subtest, 'rm', [c_name], verbose=True)
        cmdresult = dkrcmd.execute()
        if cmdresult.exit_status != 0:
            error.TestNAError("Failed to cleanup env for test: %s" %
                              (cmdresult))

    def run_once(self):
        super(simple, self).run_once()  # Prints out basic info
        self.loginfo("Starting docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        # Save image
        save_cmd = self.config['save_cmd']
        self.sub_stuff['save_ar'] = (save_cmd %
                                     {"image": self.sub_stuff["rand_name"]})

        dkrcmd = DockerCmd(self.parent_subtest, 'save',
                           [self.sub_stuff['save_ar']],
                           verbose=True)
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmdresult_save'] = dkrcmd.execute()

        if self.sub_stuff['cmdresult_save'].exit_status != 0:
            # Pass error to postprocess
            return

        # Delete image
        dkrcmd = DockerCmd(self.parent_subtest, 'rmi',
                           [self.sub_stuff["rand_name"]],
                           verbose=True)
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmdresult_del'] = dkrcmd.execute()

        # Load image
        load_cmd = self.config['load_cmd']
        self.sub_stuff['load_ar'] = (load_cmd %
                                     {"image": self.sub_stuff["rand_name"]})

        dkrcmd = DockerCmd(self.parent_subtest, 'load',
                           [self.sub_stuff['load_ar']],
                           verbose=True)
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmdresult_load'] = dkrcmd.execute()

    def postprocess(self):
        super(simple, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected

        OutputGood(self.sub_stuff['cmdresult_save'])
        OutputGood(self.sub_stuff['cmdresult_load'])

        str_save = self.sub_stuff['cmdresult_save']
        str_load = self.sub_stuff['cmdresult_load']
        str_del = self.sub_stuff['cmdresult_del']

        self.failif(str_save.exit_status != 0,
                    "Problem with save cmd detail :%s" %
                    str_save)

        self.failif(str_load.exit_status != 0,
                    "Problem with load cmd detail :%s" %
                    str_load)

        self.failif(str_del.exit_status != 0,
                    "Problem with del cmd detail :%s" %
                    str_del)

        img_name = self.sub_stuff["rand_name"]
        images = self.sub_stuff["img"].list_imgs_with_full_name(img_name)
        self.failif(images == [], "Unable to find loaded image.")

    def cleanup(self):
        super(simple, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        image_path = os.path.join("/tmp/", self.sub_stuff["rand_name"])
        self.logdebug("Removing image file %s", image_path)
        os.remove(image_path)
