"""
Summary
----------

Test output of ``docker`` import/export command

Operational Summary
----------------------

#. Prepare container for export
#. Export image to stdout
#. Import image from stdin.
#. Check image.
"""

from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers
from dockertest.images import DockerImages
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest import xceptions
from dockertest import subtest


class import_export(subtest.SubSubtestCaller):
    config_section = 'docker_cli/import_export'


class import_export_base(SubSubtest):

    def init_test_container(self, name):
        self.sub_stuff["subargs"].insert(0, "--name=\"%s\"" % name)
        dkrcmd = DockerCmd(self, 'run', self.sub_stuff['subargs'],
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
        import_dkrcmd = DockerCmd(self, "import", import_arg_csv.split(','))
        # Actually executed command
        export_args = export_arg_csv.split(',')
        export_args.append(import_dkrcmd.command)
        export_import_dkrcmd = DockerCmd(self, "export", export_args)
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
        self.sub_stuff["cont"] = DockerContainers(self)

    def cleanup(self):
        super(import_export_base, self).cleanup()
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            dc.clean_all(self.sub_stuff.get("containers"))
            di = DockerImages(self)
            di.clean_all(self.sub_stuff.get("images"))


class simple(import_export_base):

    def initialize(self):
        super(simple, self).initialize()
        # Test container setup
        dc = DockerContainers(self)
        c_name = dc.get_unique_name()
        self.sub_stuff["containers"].append(c_name)
        self.init_test_container(c_name)
        # export/import command setup
        di = DockerImages(self)
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
        self.sub_stuff['cmdresult'] = mustpass(export_import_dkrcmd.execute())

    def postprocess(self):
        super(simple, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        cmdresult = self.sub_stuff['cmdresult']
        OutputGood(cmdresult)
        self.failif_ne(cmdresult.exit_status, 0,
                       "Problem with export import cmd detail :%s" %
                       cmdresult)
