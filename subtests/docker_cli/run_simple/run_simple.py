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


class run_simple(SubSubtestCaller):
    config_section = 'docker_cli/run_simple'


class run_base(SubSubtest):

    def init_subargs(self):
        self.sub_stuff['subargs'] = self.config['run_options_csv'].split(',')
        fin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['subargs'].append(fin)
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
        # Fail test if bad command or other stdout/stderr problems detected
        OutputGood(self.sub_stuff['cmdresult'])
        expected = self.config['exit_status']
        self.failif(self.sub_stuff['cmdresult'].exit_status != expected,
                    "Exit status of /bin/true non-zero: %s"
                    % self.sub_stuff['cmdresult'])
        self.logdebug(self.sub_stuff['cmdresult'])

    def cleanup(self):
        super(run_base, self).cleanup()
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


class run_true(run_base):
    pass  # Only change is in configuration


class run_false(run_base):
    pass  # Only change is in configuration
