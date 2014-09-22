r"""
Summary
----------

Test output of docker rmi command

Operational Summary
----------------------

#. Create new Image
#. Try to delete image.
#. Check if image was deleted.

Prerequisites
----------------------
*  Image on remote registry with 'latest' and some other tag

Configuration
--------------------------------------
*  The ``docker_rmi_force`` option causes sub-subtests to force remove images
*  ``docker_expected_result`` should be "PASS" or "FAIL" to indicate result
   handling behavior of sub-subtests.
"""

import time
# FIXME: distutils.version is incorrectly missing in Travis CI, disable warning
from distutils.version import LooseVersion  # pylint: disable=E0611
from autotest.client import utils
from dockertest import subtest
from dockertest import config
from dockertest import images
from dockertest.subtest import SubSubtest
from dockertest.images import DockerImages
from dockertest.output import OutputGood
from dockertest.output import DockerVersion
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.xceptions import DockerCommandError
from dockertest.xceptions import DockerTestNAError


class rmi(subtest.SubSubtestCaller):
    config_section = 'docker_cli/rmi'

    def initialize(self):
        super(rmi, self).initialize()
        base_image = images.DockerImage.full_name_from_defaults(self.config)
        self.stuff['base_image'] = base_image


class rmi_base(SubSubtest):

    #: The --run option marked for deprecation in this version and later
    commit_run_deprecated_version = "1.1.1"

    def initialize(self):
        super(rmi_base, self).initialize()
        config.none_if_empty(self.config)

        self.sub_stuff["image_name"] = None
        self.sub_stuff["containers"] = []

    def run_once(self):
        super(rmi_base, self).run_once()
        # 1. Run with no options
        dkrcmd = AsyncDockerCmd(self, 'rmi',
                                self.complete_docker_command_line(),
                                self.config['docker_rmi_timeout'],
                                True)
        self.loginfo("Executing background command: %s" % dkrcmd)
        dkrcmd.execute()
        while not dkrcmd.done:
            self.loginfo("Deleting image...")
            time.sleep(3)
        self.sub_stuff["cmdresult"] = dkrcmd.wait()

    def remove_lock_container(self):
        prep_changes = DockerCmd(self, "rm",
                                 [self.sub_stuff["container"]],
                                 self.config['docker_rmi_timeout'])

        results = prep_changes.execute()
        if results.exit_status:
            raise DockerTestNAError("Problems during initialization of"
                                    " test: %s", results)

    def complete_docker_command_line(self):
        cmds = []

        if self.config["docker_rmi_force"]:
            cmds.append("-f")

        cmds.append(self.sub_stuff["image_name"])

        self.sub_stuff["rmi_cmd"] = cmds

        return cmds

    def postprocess(self):
        super(rmi_base, self).postprocess()
        if self.config["docker_expected_result"] == "PASS":
            # Raise exception if problems found
            OutputGood(self.sub_stuff['cmdresult'])
            self.failif(self.sub_stuff['cmdresult'].exit_status != 0,
                        "Non-zero rmi exit status: %s"
                        % self.sub_stuff['cmdresult'])

            im = self.check_image_exists(self.sub_stuff["image_name"])
            self.sub_stuff['image_list'] = im
            self.failif(im != [], "Deleted image still exits: %s" %
                        self.sub_stuff["image_name"])

        elif self.config["docker_expected_result"] == "FAIL":
            self.failif(self.sub_stuff['cmdresult'].exit_status == 0,
                        "Zero rmi exit status: Command should fail due to"
                        " wrong command arguments.")
        else:
            self.failif(True, ("Config. option 'docker_expected_result' "
                               "must be 'PASS' or 'FAIL', not %s"
                               % self.config["docker_expected_result"]))

    def cleanup(self):
        super(rmi_base, self).cleanup()
        di = DockerImages(self.parent_subtest)
        # Auto-converts "yes/no" to a boolean
        if (self.config['remove_after_test'] and
                'image_list' in self.sub_stuff):
            for cont in self.sub_stuff["containers"]:
                clean_cont = NoFailDockerCmd(self, "rm",
                                             ['--force', cont],
                                             self.config['docker_rmi_timeout'])
                clean_cont.execute()
            for image in self.sub_stuff["image_list"]:
                # If removal by name fails, try id
                try:
                    try:
                        di.remove_image_by_full_name(image.full_name)
                    except DockerCommandError:
                        di.remove_image_by_id(image.long_id)
                except DockerCommandError:
                    self.logwarning("Image not exist or failed"
                                    " to remove image.")
                self.loginfo("Successfully removed test image")

    def check_image_exists(self, full_name):
        di = DockerImages(self.parent_subtest)
        return di.list_imgs_with_full_name(full_name)

    # FIXME: Clobber this method when 'commit_run_params' goes away (below)
    def run_is_deprecated(self):
        dv = DockerVersion(NoFailDockerCmd(self, "version").execute().stdout)
        client_version = LooseVersion(dv.client)
        dep_version = LooseVersion(self.commit_run_deprecated_version)
        if client_version < dep_version:
            return False
        else:
            return True


class with_blocking_container_by_tag(rmi_base):

    """
    Test output of docker rmi command

    docker rmi full_name

    1. Create new image with full_name (tag) from image (base_image)
    2. Use new image by new container (docker run image...)
    3. Try to remove new image identified by full_name
    4. Check if command fails
    5. Check if full_name not exits in images.
    6. Remove blocking container and created image.
    """

    config_section = 'docker_cli/rmi/with_blocking_container_by_tag'

    def initialize(self):
        super(with_blocking_container_by_tag, self).initialize()

        rand_data = utils.generate_random_string(5)
        self.sub_stuff["rand_data"] = rand_data

        di = DockerImages(self.parent_subtest)
        name_prefix = self.config["rmi_repo_tag_name_prefix"]
        self.sub_stuff["image_name"] = di.get_unique_name(name_prefix)

        cmd_with_rand = self.config['docker_data_prepare_cmd'] % (rand_data)

        prep_changes = DockerCmd(self, "run",
                                 ["-d",
                                  self.parent_subtest.stuff['base_image'],
                                  cmd_with_rand],
                                 self.config['docker_commit_timeout'])

        dnamsg = ("Problems during initialization of"
                  " test: %s")
        prep_changes.execute()
        if prep_changes.cmdresult.exit_status:
            raise DockerTestNAError(dnamsg % prep_changes.cmdresult)
        else:
            self.sub_stuff["container"] = prep_changes.cmdresult.stdout.strip()
            self.sub_stuff["containers"].append(self.sub_stuff["container"])
        # Private to this instance, outside of __init__

        dkrcmd = DockerCmd(self, 'commit',
                           self.complete_commit_command_line(),
                           self.config['docker_commit_timeout'])
        dkrcmd.execute()
        if dkrcmd.cmdresult.exit_status:
            raise DockerTestNAError(dnamsg % dkrcmd.cmdresult)

        args = ["-d", self.sub_stuff["image_name"], cmd_with_rand]
        prep_changes = DockerCmd(self, "run", args,
                                 self.config['docker_commit_timeout'])

        prep_changes.execute()
        if prep_changes.cmdresult.exit_status:
            raise DockerTestNAError(dnamsg % dkrcmd.cmdresult)
        else:
            prep_stdout = prep_changes.cmdresult.stdout.strip()
            self.sub_stuff["containers"].append(prep_stdout)

        im = self.check_image_exists(self.sub_stuff["image_name"])
        self.sub_stuff['image_list'] = im

    def complete_commit_command_line(self):
        c_author = self.config["commit_author"]
        c_msg = self.config["commit_message"]
        # FIXME: Remove commit_run_params entirely in future version
        run_params = self.config.get("commit_run_params")
        repo_addr = self.sub_stuff["image_name"]

        cmds = []
        if c_author:
            cmds.append("-a %s" % c_author)
        if c_msg:
            cmds.append("-m %s" % c_msg)
        if run_params and not self.run_is_deprecated():
            cmds.append("--run=%s" % run_params)

        cmds.append(self.sub_stuff["container"])

        cmds.append(repo_addr)

        self.sub_stuff["commit_cmd"] = cmds

        return cmds

    def _common_post(self):
        # Raise exception if problems found
        OutputGood(self.sub_stuff['cmdresult'],
                   skip=['error_check'])  # error is expected
        self.failif(self.sub_stuff['cmdresult'].exit_status == 0,
                    "Zero rmi exit status: Command should fail due to"
                    " wrong image name.")

    def postprocess(self):
        self._common_post()
        im = self.check_image_exists(self.sub_stuff["image_name"])
        self.failif(im != [], "Tag should be possible delete even if image"
                              " %s is still used by container." %
                    self.sub_stuff["image_name"])


class with_blocking_container_by_id(with_blocking_container_by_tag):

    """
    Test output of docker Pull command

    docker rmi full_name

    1. Create new image with full_name (tag) from image (base_image)
    2. Use new image by new container (docker run image...)
    3. Try to remove new image by image id
    4. Check if command fails
    5. Remove blocking container and created image.
    """
    config_section = 'docker_cli/rmi/with_blocking_container_by_id'

    def initialize(self):
        super(with_blocking_container_by_id, self).initialize()

        im = self.check_image_exists(self.sub_stuff["image_name"])
        self.sub_stuff["image_name"] = im[0].long_id

    def postprocess(self):
        self._common_post()
        im = self.check_image_exists_by_id(self.sub_stuff["image_name"])
        self.failif(im == [], "Used images [%s] was deleted."
                              "It shouldn't be possible." %
                    self.sub_stuff["image_name"])

    def check_image_exists_by_id(self, image_id):
        di = DockerImages(self.parent_subtest)
        return di.list_imgs_with_image_id(image_id)
