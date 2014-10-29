r"""
Summary
----------

Test docker run by executing basic commands inside container and checking the
results.

Operational Summary
----------------------

#.  Test Container image with a ``/bin/true`` executable returning zero
#.  Test Container image with a ``/bin/false`` executable returning non-zero
#.  Test accurate (relative to host) timekeeping in running container
#.  Test run requiring pulling an image down automatically
#.  Smoke-test running container receiving signals
#.  Smoke-test attaching to a running container
#.  Smoke-test disconnecting from a running container
"""

from dockertest.subtest import SubSubtest, SubSubtestCaller
from dockertest.dockercmd import DockerCmd
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.output import OutputGood
from autotest.client.shared import error


class run(SubSubtestCaller):
    config_section = 'docker_cli/run'


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
        dkrcmd = DockerCmd(self, 'run', self.sub_stuff['subargs'])
        dkrcmd.verbose = True
        self.sub_stuff['dkrcmd'] = dkrcmd
        dkrcmd.execute()

    def postprocess(self):
        super(run_base, self).postprocess()  # Prints out basic info
        if 'dkrcmd' in self.sub_stuff:
            # Fail test if bad command or other stdout/stderr problems detected
            OutputGood(self.sub_stuff['dkrcmd'].cmdresult)
            expected = self.config['exit_status']
            self.failif(self.sub_stuff['dkrcmd'].exit_status != expected,
                        "Exit status non-zero command %s"
                        % self.sub_stuff['dkrcmd'].cmdresult)
            self.logdebug(self.sub_stuff['dkrcmd'].cmdresult)

    def cleanup(self):
        super(run_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['remove_after_test']:
            for cont in self.sub_stuff.get("containers", []):
                dkrcmd = DockerCmd(self, "rm", ['--volumes', '--force', cont])
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
                    if error_text not in e.result_obj.stderr:
                        raise


class run_true(run_base):
    pass  # Only change is in configuration


class run_false(run_base):
    pass  # Only change is in configuration


class run_names(run_base):
    # Verify behavior when multiple --name options passed

    def initialize(self):
        super(run_names, self).initialize()
        cont = self.sub_stuff["cont"]
        names = []
        for number in xrange(self.config['names_count']):
            names.append(cont.get_unique_name(suffix=str(number)))
        subargs = self.sub_stuff['subargs']
        self.sub_stuff['subargs'] = ["--name %s" % n for n in names] + subargs
        if self.config['last_name_sticks']:
            self.sub_stuff['expected_name'] = names[-1]
        else:
            self.sub_stuff['expected_name'] = names[0]

    def run_once(self):
        super(run_names, self).run_once()
        cid = self.sub_stuff['cid'] = self.sub_stuff['dkrcmd'].stdout.strip()
        self.sub_stuff['containers'].append(cid)
        try:
            self.sub_stuff["cont"].wait_by_long_id(cid)
        except ValueError:
            pass  # container already finished and exited

    def postprocess(self):
        super(run_names, self).postprocess()
        cont = self.sub_stuff["cont"]
        json = cont.json_by_long_id(self.sub_stuff['cid'])
        self.failif(len(json) == 0)
        # docker sticks a "/" prefix on name (documented?)
        actual_name = str(json[0]['Name'][1:])
        self.failif(actual_name != self.sub_stuff['expected_name'],
                    "Actual name %s != expected name %s"
                    % (actual_name, self.sub_stuff['expected_name']))
