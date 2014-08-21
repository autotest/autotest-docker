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

from autotest.client import utils
from autotest.client.shared import error
from dockertest import subtest
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage, DockerImages
from dockertest.output import OutputGood
from dockertest.subtest import SubSubtest


class save_load(subtest.SubSubtestCaller):

    """ Subtest caller """


class save_load_base(SubSubtest):

    """ Initialize couple of variables and removes all containters/images """

    def _init_container(self, name, cmd):
        """
        :return: tuple(container_cmd, container_name)
        """
        if self.config.get('run_options_csv'):
            subargs = [arg for arg in
                       self.config['run_options_csv'].split(',')]
        else:
            subargs = []
        if name is True:
            name = self.sub_stuff['cont'].get_unique_name("test", length=4)
        elif name:
            name = name
        if name:
            subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append(cmd)
        container = DockerCmd(self, 'run', subargs, verbose=False)
        return container, name

    def initialize(self):
        super(save_load_base, self).initialize()
        self.sub_stuff["containers"] = []
        self.sub_stuff["images"] = []
        self.sub_stuff["cont"] = DockerContainers(self)
        self.sub_stuff["img"] = DockerImages(self)

    def cleanup(self):
        super(save_load_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['remove_after_test']:
            for cont in self.sub_stuff["containers"]:
                dkrcmd = DockerCmd(self, "rm", ['--volumes', '--force', cont])
                cmdresult = dkrcmd.execute()
                msg = (" removed test container: %s" % cont)
                if cmdresult.exit_status == 0:
                    self.logdebug("Successfully" + msg)
                else:
                    self.logwarning("Failed" + msg)
            for image in self.sub_stuff["images"]:
                try:
                    dkrimg = self.sub_stuff['img']
                    self.logdebug("Removing image %s", image)
                    dkrimg.remove_image_by_full_name(image)
                    self.logdebug("Successfully removed test image: %s",
                                  image)
                except error.CmdError, exc:
                    error_text = "tagged in multiple repositories"
                    if error_text not in exc.result_obj.stderr:
                        raise


class simple(save_load_base):

    """ Basic test, executes container, saves it and loads it again. """

    def initialize(self):
        super(simple, self).initialize()
        rand_name = utils.generate_random_string(8).lower()
        self.sub_stuff["rand_name"] = rand_name

        self.sub_stuff['containers'].append(rand_name)
        self.sub_stuff["images"].append(rand_name)

        dkrcmd = self._init_container(rand_name,
                                      self.config['docker_data_prep_cmd'])[0]

        cmdresult = dkrcmd.execute()
        if cmdresult.exit_status != 0:
            error.TestNAError("Unable to prepare env for test: %s" %
                              (cmdresult))

        rand_name = self.sub_stuff["rand_name"]
        cid = self.sub_stuff["cont"].list_containers_with_name(rand_name)

        self.failif(cid == [],
                    "Unable to search container with name %s: details :%s" %
                    (rand_name, cmdresult))

        dkrcmd = DockerCmd(self, 'commit', [rand_name, rand_name])

        cmdresult = dkrcmd.execute()
        if cmdresult.exit_status != 0:
            error.TestNAError("Unable to prepare env for test: %s" %
                              (cmdresult))
        dkrcmd = DockerCmd(self, 'rm', [rand_name])
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
                                     {"image": self.sub_stuff["rand_name"],
                                      "tmpdir": self.tmpdir})

        dkrcmd = DockerCmd(self, 'save',
                           [self.sub_stuff['save_ar']],
                           verbose=True)
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmdresult_save'] = dkrcmd.execute()

        if self.sub_stuff['cmdresult_save'].exit_status != 0:
            # Pass error to postprocess
            return

        # Delete image
        dkrcmd = DockerCmd(self, 'rmi',
                           [self.sub_stuff["rand_name"]],
                           verbose=True)
        # Runs in background
        self.sub_stuff['cmdresult_del'] = dkrcmd.execute()

        # Load image
        load_cmd = self.config['load_cmd']
        self.sub_stuff['load_ar'] = (load_cmd %
                                     {"image": self.sub_stuff["rand_name"],
                                      "tmpdir": self.tmpdir})

        dkrcmd = DockerCmd(self, 'load',
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
