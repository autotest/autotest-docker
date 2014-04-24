"""
Test output of docker import/export command
"""

from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers
from dockertest.images import DockerImages
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import NoFailDockerCmd
from dockertest import xceptions
from dockertest import subtest

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


class import_export(subtest.SubSubtestCaller):
    config_section = 'docker_cli/import_export'


class import_export_base(SubSubtest):

    def init_test_container(self, name):
        self.sub_stuff["subargs"].insert(0, "--name=\"%s\"" % name)
        dkrcmd = DockerCmd(self.parent_subtest, 'run',
                           self.sub_stuff['subargs'],
                           timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True
        cmdresult = dkrcmd.execute()
        if cmdresult.exit_status != 0:
            xceptions.DockerTestNAError("Unable to prepare env for test: %s" %
                                       (cmdresult))
        cid = self.sub_stuff["cont"].list_containers_with_name(name)
        self.failif(cid == [],
                    "Unable to search container with name %s: details :%s" %
                   (name, cmdresult))

    def init_ei_dockercmd(self, export_arg_csv, import_arg_csv):
        # Never execute()'d, just used for command property
        import_dkrcmd = DockerCmd(self.parent_subtest,
                                  "import", import_arg_csv.split(','))
        # Actually executed command
        export_args = export_arg_csv.split(',')
        export_args.append(import_dkrcmd.command)
        export_import_dkrcmd = NoFailDockerCmd(self.parent_subtest,
                                               "export", export_args)
        export_import_dkrcmd.verbose = True
        self.sub_stuff['export_import_dkrcmd'] = export_import_dkrcmd

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
                except xceptions.DockerCommandError, e:
                    error_text = "tagged in multiple repositories"
                    if not error_text in e.result_obj.stderr:
                        raise
                except xceptions.DockerTestError:
                    pass  # best effort removal, maybe image wasn't there

class simple(import_export_base):

    def initialize(self):
        super(simple, self).initialize()
        # Test container setup
        dc = DockerContainers(self.parent_subtest)
        c_name = dc.get_unique_name(self.__class__.__name__)
        self.sub_stuff["containers"].append(c_name)
        self.init_test_container(c_name)
        # export/import command setup
        di = DockerImages(self.parent_subtest)
        i_name = di.get_unique_name(c_name)  # easier debugging
        self.sub_stuff["images"].append(i_name)
        subdct = {"container": c_name, "image": i_name}
        export_cmd_args = self.config['export_cmd_args'].strip() % subdct
        import_cmd_args = self.config['import_cmd_args'].strip() % subdct
        self.init_ei_dockercmd(export_cmd_args, import_cmd_args)

    def run_once(self):
        super(simple, self).run_once()
        export_import_dkrcmd = self.sub_stuff['export_import_dkrcmd']
        self.loginfo("Starting %s", export_import_dkrcmd)
        self.sub_stuff['cmdresult'] = export_import_dkrcmd.execute()

    def postprocess(self):
        super(simple, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        cmdresult = self.sub_stuff['cmdresult']
        OutputGood(cmdresult)
        self.failif(cmdresult.exit_status != 0,
                    "Problem with export import cmd detail :%s" %
                    cmdresult)
