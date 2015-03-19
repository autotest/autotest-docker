r"""
Summary
----------

Test docker create by executing basic commands inside container and checking
the results.

Operational Summary
----------------------

#.  Create container with ``/bin/true`` command verify zero-exit status
#.  Create container with ``/bin/false`` command verify **zero** exit status
#.  Create container from image that doesn't exist locally
#.  Create container, send signal to created container.
"""

from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.output import OutputGood
from dockertest.config import get_as_list
from dockertest.xceptions import DockerTestError


class create(SubSubtestCaller):
    pass


class create_base(SubSubtest):

    def init_subargs_imgcmd(self):
        fqin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['fqin'] = fqin
        self.sub_stuff['subargs'].append(fqin)
        self.sub_stuff['subargs'] += get_as_list(self.config['bash_cmd'])
        self.sub_stuff['subargs'].append(self.config['cmd'])

    def init_utilities(self):
        self.sub_stuff["cont"] = DockerContainers(self)
        self.sub_stuff["img"] = DockerImages(self)

    def init_name(self):
        self.sub_stuff['name'] = DockerContainers(self).get_unique_name()
        self.sub_stuff['subargs'] += ['--name', self.sub_stuff['name']]

    def get_cid(self, dkrcmd=None):
        if dkrcmd is None:
            dkrcmd = self.sub_stuff['dkrcmd']
        if dkrcmd is not None:
            lines = dkrcmd.stdout.strip().splitlines()
            return lines[-1].strip()
        else:
            raise DockerTestError("Docker command %s execution state missing"
                                  % dkrcmd)

    def initialize(self):
        super(create_base, self).initialize()
        self.sub_stuff['dkrcmd'] = None
        self.init_utilities()
        self.sub_stuff['subargs'] = get_as_list(self.config['run_options_csv'])
        self.init_name()
        self.init_subargs_imgcmd()

    def run_once(self):
        super(create_base, self).run_once()    # Prints out basic info
        dkrcmd = DockerCmd(self, 'create', self.sub_stuff['subargs'])
        self.sub_stuff['dkrcmd'] = dkrcmd
        dkrcmd.execute()

    def postprocess(self):
        super(create_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        dkrcmd = self.sub_stuff['dkrcmd']
        OutputGood(dkrcmd.cmdresult)
        expected = 0  # always
        self.failif(dkrcmd.exit_status != expected,
                    "Exit status non-zero command %s"
                    % dkrcmd.cmdresult)
        # cid must be printed on stdout, always
        cid = self.get_cid()
        # non-forced removal must succeed, rely on rm test to verify.
        mustpass(DockerCmd(self, 'rm', [cid]).execute())

    def cleanup(self):
        super(create_base, self).cleanup()
        if self.config['remove_after_test']:
            preserve_cnames = get_as_list(self.config['preserve_cnames'])
            # One last cleanup try based on what is known
            if self.sub_stuff['name'] not in preserve_cnames:
                DockerCmd(self, 'rm', ['--force', '--volumes',
                                       self.sub_stuff['name']]).execute()


class create_true(create_base):
    pass  # Only change is in configuration


class create_false(create_base):
    pass  # Only change is in configuration
