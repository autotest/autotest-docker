r"""
Summary
----------

Test docker run by command(s) inside container and checking the
results.

Operational Summary
----------------------

#.  Form docker command line from configuration options
#.  Execute docker command
#.  PASS/FAIL based on configuration and executed command output/results
"""

from dockertest.subtest import SubSubtest, SubSubtestCaller
from dockertest.dockercmd import DockerCmd
from dockertest.containers import DockerContainers
from dockertest.images import DockerImages
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.config import Config
from dockertest.config import get_as_list


class run(SubSubtestCaller):
    pass


class run_base(SubSubtest):

    def init_image(self):
        fqin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['fqin'] = fqin

    def init_subargs(self):
        subargs = self.sub_stuff['subargs']
        subargs += get_as_list(self.config['run_options_csv'])
        if self.config['run_append_name'] is True:
            dc = self.sub_stuff["cont"]
            name = dc.get_unique_name()
            self.sub_stuff['name'] = name
            self.sub_stuff['containers'].append(name)
            subargs.append('--name')
            subargs.append(name)
        fqin = self.sub_stuff['fqin']
        subargs.append(fqin)
        subargs += get_as_list(self.config['bash_cmd'])
        subargs.append(self.config['cmd'])

    def init_dockercmd(self):
        dkrcmd = DockerCmd(self, 'run', self.sub_stuff['subargs'],
                           verbose=True)
        self.sub_stuff['dkrcmd'] = dkrcmd

    def initialize(self):
        super(run_base, self).initialize()
        self.sub_stuff['fqin'] = ''
        self.sub_stuff['dkrcmd'] = None
        self.sub_stuff['stdin'] = None
        self.sub_stuff['subargs'] = []
        self.sub_stuff["containers"] = []
        self.sub_stuff["images"] = []
        self.sub_stuff["cont"] = DockerContainers(self)
        self.sub_stuff["img"] = DockerImages(self)
        self.init_image()
        self.init_subargs()
        self.init_dockercmd()

    def run_once(self):
        super(run_base, self).run_once()    # Prints out basic info
        self.sub_stuff['dkrcmd'].execute(self.sub_stuff['stdin'])

    def postprocess(self):
        super(run_base, self).postprocess()  # Prints out basic info
        dockercmd = self.sub_stuff['dkrcmd']
        OutputGood(dockercmd.cmdresult)
        expected = self.config['exit_status']
        self.failif(dockercmd.exit_status != expected,
                    "Exit status %d, expected %d"
                    % (dockercmd.exit_status, expected))

    def cleanup(self):
        super(run_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        if self.config['remove_after_test']:
            for cont in self.sub_stuff.get("containers", []):
                dkrcmd = DockerCmd(self, "rm", ['--volumes', '--force', cont])
                dkrcmd.execute()
            for image in self.sub_stuff.get("images", []):
                dkrcmd = DockerCmd(self, "rmi", ['--force', image])
                dkrcmd.execute()


# Generate any generic sub-subtests configured 'generate_generic = yes'
def generic_run_factory(name):

    class GenericRun(run_base):
        pass

    GenericRun.__name__ = name
    return GenericRun

subname = 'docker_cli/run'
config = Config()
subsubnames = get_as_list(config[subname]['subsubtests'])
ssconfigs = []
globes = globals()
for ssname in subsubnames:
    fullname = '%s/%s' % (subname, ssname)
    if fullname in config:
        ssconfig = config[fullname]
        if ssconfig.get('generate_generic', False):
            ssconfigs.append(ssconfig)
            cls = generic_run_factory(ssname)
            # Inject generated class into THIS module's namespace
            globes[cls.__name__] = cls
