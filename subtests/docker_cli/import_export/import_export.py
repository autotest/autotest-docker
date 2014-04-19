"""
Test output of docker import/export command
"""

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


class import_export(subtest.SubSubtestCaller):
    config_section = 'docker_cli/import_export'


class import_export_base(SubSubtest):

    def initialize(self):
        super(import_export_base, self).initialize()
        self.sub_stuff['subargs'] = self.config['run_options_csv'].split(',')
        fin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['subargs'].append(fin)
        self.sub_stuff['subargs'].append(self.config['docker_data_prep_cmd'])
        self.sub_stuff["containers"] = []
        self.sub_stuff["images"] = []
        self.sub_stuff["cont"] = DockerContainers(self.parent_subtest)

    def cleanup(self):
        super(import_export_base, self).cleanup()
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


class simple(import_export_base):

    def initialize(self):
        super(simple, self).initialize()
        rand_name = utils.generate_random_string(8).lower()
        self.sub_stuff["rand_name"] = rand_name
        self.sub_stuff["subargs"].insert(0, "--name=\"%s\"" % rand_name)

        dkrcmd = DockerCmd(self.parent_subtest, 'run',
                           self.sub_stuff['subargs'],
                           timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True

        # Runs in background
        cmdresult = dkrcmd.execute()
        if cmdresult.exit_status != 0:
            error.TestNAError("Unable to prepare env for test: %s" %
                              (cmdresult))

        import_export_cmd = self.config['import_export_cmd']
        self.sub_stuff['subargs_ei'] = (import_export_cmd %
                                        {"container": rand_name})

        c_name = self.sub_stuff["rand_name"]
        self.sub_stuff["containers"].append(c_name)
        self.sub_stuff["images"].append(c_name)
        cid = self.sub_stuff["cont"].list_containers_with_name(c_name)

        self.failif(cid == [],
                    "Unable to search container with name %s: details :%s" %
                   (c_name, cmdresult))

    def run_once(self):
        self.loginfo("Starting background docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        dkrcmd = DockerCmd(self.parent_subtest, 'export',
                           [self.sub_stuff['subargs_ei']],
                           timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmdresult_import_export'] = dkrcmd.execute()

    def postprocess(self):
        super(import_export_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected

        OutputGood(self.sub_stuff['cmdresult_import_export'])

        str_import_export = self.sub_stuff['cmdresult_import_export']
        self.failif(str_import_export.exit_status != 0,
                    "Problem with export import cmd detail :%s" %
                    str_import_export)
