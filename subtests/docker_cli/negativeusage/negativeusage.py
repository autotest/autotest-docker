"""
Summary
---------

Negative testing for many different malformed docker CLI sub-commands.

Operational Summary
----------------------

#. Form a docker sub-command based on configured values, though missing
   some key, required part (parameter value, option value, out-of-order
   required options, etc.).
#. Execute malformed command, verify exit status, stdout, and stderr all
   match expected values.

Operational Detail
----------------------

Sub-subtests are organized with names according to the following
legend, with a number appended:

``op``:
        Omit Positional - leave out a required positional parameter
``if``:
        Invalid Flag - Addition of non-existing flag
``ov``:
        Omit Value - Leave out required value to argument (make it like a flag)
``iv``:
        Invalid Value - Give improper/incorrect value to argument
``ip``:
        Invalid Positional - Give value to non-existing positional parameter
"""

import re
from dockertest import subtest
from dockertest import containers
from dockertest import dockercmd
from dockertest import images
from dockertest import config
from dockertest import output
from dockertest import xceptions
from dockertest.output import mustpass


class NoisyCmd(dockercmd.DockerCmd):

    """
    Central to test, guarantee verbose/non-quiet even if defaults change
    """
    verbose = True
    quiet = False


# Only scan for indication of a go panic/crash
class NoPanic(output.OutputGoodBase):
    crash_check = staticmethod(output.OutputGood.crash_check)


class negativeusage(subtest.SubSubtestCaller):

    def initialize(self):
        super(negativeusage, self).initialize()
        dc = self.stuff['dc'] = containers.DockerContainers(self)
        dc.remove_args = '--force --volumes'
        ecs = self.stuff['existing_containers'] = dc.list_container_ids()
        di = self.stuff['di'] = images.DockerImages(self)
        eis = self.stuff['existing_images'] = di.list_imgs_full_name()
        self.logdebug("Containers existing before test: %s", ecs)
        self.logdebug("Images existing before test: %s", eis)

    def cleanup(self):
        # Cannot predict what images/containers will be created
        # clean everything not existing in initialize()
        super(negativeusage, self).cleanup()
        if not self.config['remove_after_test']:
            return
        preserve_fqins = config.get_as_list(self.config['preserve_fqins'])
        preserve_cnames = config.get_as_list(self.config['preserve_cnames'])
        dc = self.stuff['dc']
        ecs = self.stuff['existing_containers'] + preserve_cnames
        di = self.stuff['di']
        eis = self.stuff['existing_images'] + [di.default_image]
        eis += preserve_fqins
        for cid in dc.list_container_ids():
            if cid not in ecs:
                # Sub-subtests should have cleaned up for themselves
                self.logwarning("Removing container %s", cid)
                dockercmd.DockerCmd(self, 'rm', ['--force', cid]).execute()
        # Don't clean default image
        for full_name in di.list_imgs_full_name():
            if full_name not in eis:
                # Sub-subtests should have cleaned up for themselves
                self.logwarning("Removing image: %s", full_name)
                di.remove_image_by_full_name(full_name)
                dockercmd.DockerCmd(self, 'rmi',
                                    ['--force', full_name]).execute()


class Base(subtest.SubSubtest):

    def init_utilities(self):
        dc = self.sub_stuff['dc'] = containers.DockerContainers(self)
        dc.remove_args = '--force --volumes'
        dc.verify_output = True
        di = self.sub_stuff['di'] = images.DockerImages(self)
        di.verify_output = True

    def init_subcntrs(self):
        # Called from init_substitutions
        cntr = dockercmd.AsyncDockerCmd(self, 'run',
                                        ['--detach',
                                         self.sub_stuff['FQIN'],
                                         'sleep 5m'],
                                        verbose=False)
        cntr.execute()
        # cntr.stdout is a property
        if output.wait_for_output(lambda: cntr.stdout, r'^\w{64}$'):
            self.sub_stuff['RUNCNTR'] = cntr.stdout.splitlines()[-1].strip()
        else:
            raise xceptions.DockerTestNAError("Failed to initialize %s"
                                              % self.config_section)
        # Throw away cntr, all we need is the CID
        cntr = mustpass(dockercmd.DockerCmd(self, 'run',
                                            ['--detach',
                                             self.sub_stuff['FQIN'], 'true'],
                                            verbose=False).execute())
        # Only the CID is needed
        self.sub_stuff['STPCNTR'] = cntr.stdout.splitlines()[-1].strip()

    def init_substitutions(self):
        di = self.sub_stuff['di']
        self.sub_stuff['FQIN'] = di.default_image
        fqin = di.get_unique_name()
        self.sub_stuff['NOFQIN'] = fqin
        self.init_subcntrs()

    def do_substitutions(self):
        # Some are CSV, some are regex, some are simple strings
        for key in ('subcmd', 'subarg', 'stderr', 'stdout'):
            # Ignore empty config values
            if self.config[key].strip() != '':
                # Catch misspellings / unsupported sutstitution keywords
                try:
                    value = self.config[key] % self.sub_stuff
                except KeyError, xcpt:
                    raise KeyError("Configuration error with option '%s' value"
                                   "in sub-subtest %s: Invalid substitution "
                                   "key '%s'" % (key, self.config_section,
                                                 xcpt.message))
            else:
                value = ''
            if key == 'subarg':  # This is a CSV option
                if value.strip() == '':
                    value = []
                else:
                    value = config.get_as_list(value)
            elif key in ('stderr', 'stdout'):  # This is a regex
                if value.strip() == '':
                    value = None  # Signals bypass postprocess() check
                else:
                    value = re.compile(value.strip())
            # Record possibly modified value
            self.sub_stuff[key] = value

    def initialize(self):
        super(Base, self).initialize()
        self.init_utilities()
        self.init_substitutions()
        self.do_substitutions()

    def run_once(self):
        super(Base, self).run_once()
        subcmd = self.sub_stuff['subcmd']
        subarg = self.sub_stuff['subarg']
        self.sub_stuff['cmdresult'] = NoisyCmd(self, subcmd, subarg).execute()

    def postprocess(self):
        NoPanic(self.sub_stuff['cmdresult'])
        expected_exit_status = self.config['extcmd']
        cmdresult = self.sub_stuff['cmdresult']
        self.failif(cmdresult.exit_status != expected_exit_status,
                    "Exit status was not %d:\n%s"
                    % (expected_exit_status, cmdresult))
        # Same checks for both
        for outtype in ('stdout', 'stderr'):
            if self.sub_stuff[outtype] is not None:
                regex = self.sub_stuff[outtype]
                mobj = regex.search(getattr(cmdresult, outtype))
                self.failif(mobj is None,
                            "%s did not match regex '%s':\n%s"
                            % (outtype, regex.pattern, cmdresult))

    def cleanup(self):
        super(Base, self).cleanup()
        if not self.config['remove_after_test']:
            return
        if len(self.sub_stuff.get('RUNCNTR', [])):
            dockercmd.DockerCmd(self, 'kill',
                                [self.sub_stuff['RUNCNTR']]).execute()
        if len(self.sub_stuff.get('STPCNTR', [])):
            dockercmd.DockerCmd(self, 'rm',
                                ['--force', '--volumes',
                                 self.sub_stuff['STPCNTR']]).execute()


# This _must_ happen in the top-level of main test module
# so that all sub-subtest classes exist in namespace on load.
_globals = globals()  # This modules namespace
cfg = config.Config()['docker_cli/negativeusage']  # subtest config
for sst in config.get_as_list(cfg['subsubtests']):
    # Inject generated class into top-level namespace of module
    _globals[sst] = type(sst, (Base,), {})
