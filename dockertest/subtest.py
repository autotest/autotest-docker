"""
Adapt/extend autotest.client.test.test for Docker test sub-framework

This module provides two helper classes intended to make writing
subtests easier.  They hide some of the autotest ``test.test``
complexity, while providing some helper methods for logging
output to the controlling terminal (only) and automatically
loading the specified configuration section (see `configuration module`_)
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import logging
import tempfile
import os.path
import imp
import sys
import copy
from autotest.client.shared.error import AutotestError
from autotest.client.shared.error import TestError
from autotest.client.shared.version import get_version
from autotest.client import test
import version
import config
import subtestbase
from xceptions import DockerTestFail
from xceptions import DockerTestNAError
from xceptions import DockerTestError
from xceptions import DockerSubSubtestNAError


class Subtest(subtestbase.SubBase, test.test):

    r"""
    Extends autotest test.test with dockertest-specific items

    :param \*args: Ignored and blindly passed through to super-class.
    :param \*\*dargs: Ignored and blindly passed through to super-class.
    """
    #: Version number from configuration, read-only / setup inside ``__init__``
    #: affects one-time building of bundled content in ``self.srcdir`` by
    #: controlling the call to ``setup()`` method only when it changes.
    #: Compared to ``dockertest`` API, when specified in configuration.
    #: Test will not execute if there is a MAJOR/MINOR mismatch
    #: (revision is okay).
    version = None

    #: The current iteration being run, read-only / set by the harness.
    iteration = None  # set from test.test

    #: The number of iterations to run in total, override this in subclass.
    iterations = 1

    #: Private dictionary for use by subclasses **ONLY**.  This attribute
    #: is completely ignored everywhere inside the ``dockertest`` API.
    #: Subtests are encouraged to use it for temporarily storing
    #: results/info. It is initialized to an empty dictionary, but subtests
    #: can reassign it to any type needed.
    stuff = None

    #: Private cache of control.ini's [Control] section contents (do not use!)
    _control_ini = None

    def __init__(self, *args, **dargs):

        def _make_cfgsect():
            testpath = os.path.abspath(self.bindir)
            testpath = os.path.normpath(testpath)
            dirlist = testpath.split('/')  # is there better way?
            dirlist.reverse()  # pop from the root-down
            # Throws an IndexError if list becomes empty
            while dirlist.pop() != 'subtests':
                pass  # work already done :)
            dirlist.reverse()  # correct order
            # i.e. docker_cli/run_twice
            return os.path.join(*dirlist)

        def _init_config():  # private, no docstring pylint: disable=C0111
            # So tests don't need to set this up every time
            config_parser = config.Config()
            self.config = config_parser.get(self.config_section)
            if self.config is None:
                # Try generating config_section name
                config_section = _make_cfgsect()  # not exist: need class-attr
                # instance isn't setup yet, logging doesn't work :(
                if config_section in config_parser:
                    self.config_section = config_section
                    self.config = config_parser.get(self.config_section)
                else:  # auto-generate failed
                    self.config = config_parser['DEFAULTS']
                    # Mark this to not be checked, no config, no version info.
                    self.config['config_version'] = version.NOVERSIONCHECK
                    self.version = 0
                    self.config_section = config_section
                    # just in case anything looks
                    self.config['config_section'] = config_section
            else:
                # Version number used by one-time setup() test.test method
                self.version = version.str2int(self.config['config_version'])

        def _init_logging():  # private, no docstring pylint: disable=C0111
            # Log original key/values before subtest could modify them
            self.write_test_keyval(self.config)

        super(Subtest, self).__init__(*args, **dargs)
        _init_config()
        _init_logging()
        self.check_disable(self.config_section)
        # Optionally setup different iterations if option exists
        self.iterations = self.config.get('iterations', self.iterations)
        # subclasses can do whatever they like with this
        self.stuff = {}

    @staticmethod
    def not_disabled(config_dict, config_section):
        """
        Return False if config_section (name) is in config_dict[disable]
        """
        disable = config_dict.get('disable', '')
        disabled = [thing.strip() for thing in disable.strip().split(',')]
        if len(disabled) > 0 and config_section.strip() in disabled:
            return False
        return True

    def check_disable(self, config_section):
        """
        Raise DockerTestNAError if test disabled on this host/environment
        """
        if not self.not_disabled(self.config, config_section):
            msg = "Subtest disabled in configuration."
            self.loginfo(msg)
            raise DockerTestNAError(msg)

    def execute(self, *args, **dargs):
        """**Do not override**, needed to pull data from super class"""
        super(Subtest, self).execute(iterations=self.iterations,
                                     *args, **dargs)

    # These methods can optionally be overridden by subclasses

    def setup(self):
        """
        Called once per version change
        """
        self.loginfo("setup() for subtest version %s", self.version)

    def initialize(self):
        super(Subtest, self).initialize()
        # Fail test if autotest is too old
        version.check_autotest_version(self.config, get_version())
        # Fail test if configuration being used doesn't match dockertest API
        version.check_version(self.config)
        msg = "Subtest %s configuration:\n" % self.__class__.__name__
        for key, value in self.config.items():
            msg += '\t\t%s = "%s"\n' % (key, value)
        self.logdebug(msg)

    def postprocess_iteration(self):
        """
        Called for each iteration, used to process results
        """
        self.loginfo("postprocess_iteration() #%d of #%d",
                     self.iteration, self.iterations)

    @property
    def control_config(self):
        """
        Represent operational control.ini's [Control] section as a dict or None
        """
        if self._control_ini is None:
            fullpath = os.path.join(self.job.resultdir, 'control.ini')
            # Control-file & behavior cannot be assumed, file may not exist.
            try:
                self._control_ini = config.ConfigDict('Control')
                self._control_ini.read(open(fullpath, 'rb'))
            except (IOError, OSError, config.Error):
                self.logwarning("Failed to load reference '%s' and/or"
                                "it's '[Control]' section.", fullpath)
                self._control_ini = {}
        if self._control_ini == {}:
            self.logdebug("No reference control.ini found, returning None")
            return None
        else:
            return dict(self._control_ini.items())  # return a copy


class SubSubtest(subtestbase.SubBase):

    """
    Simplistic/minimal subtest interface matched with config section

    :param parent_subtest: The Subtest instance calling this instance
    """

    #: Reference to outer, parent test.  Read-only / set in ``__init__``
    parent_subtest = None

    #: Private dictionary for use by subclasses **ONLY**.  This attribute
    #: is completely ignored everywhere inside the ``dockertest`` API.
    #: Subtests are encouraged to use it for temporarily storing
    #: results/info.  It is initialized to an empty dictionary, however
    #: subsubtests may re-assign it to any other type as needed.
    sub_stuff = None

    #: Number of additional space/tab characters to prefix when logging
    n_spaces = 16  # date/timestamp length

    #: Number of additional space/tab characters to prefix when logging
    n_tabs = 2     # two-levels

    def __init__(self, parent_subtest):
        super(SubSubtest, self).__init__()
        classname = self.__class__.__name__
        # Allow parent_subtest to use any interface this
        # class is setup to support. Don't check type.
        self.parent_subtest = parent_subtest
        # Append this subclass's name onto parent's section name
        # e.g. [parent_config_section/child_class_name]
        pscs = self.parent_subtest.config_section
        self.config_section = self.make_name(pscs)
        # Allow child to inherit and override parent config
        all_configs = config.Config()
        # make_subsubtest_config will modify this
        parent_config = self.parent_subtest.config
        # subsubtest config is optional, overrides parent.
        if self.config_section not in all_configs:
            self.config = copy.deepcopy(parent_config)
        else:
            self.config = self.make_config(all_configs,
                                           parent_config,
                                           self.config_section)
        # Not automatically logged along with parent subtest
        msg = "Sub-subtest %s configuration:\n" % self.config_section
        for key, value in self.config.items():
            msg += '\t\t%s = "%s"\n' % (key, value)
        self.logdebug(msg)
        note = {'Configuration_for_Subsubtest': self.config_section}
        self.parent_subtest.write_test_keyval(note)
        self.parent_subtest.write_test_keyval(self.config)
        self.parent_subtest.check_disable(self.config_section)
        # subclasses can do whatever they like with this
        self.sub_stuff = {}
        self.tmpdir = tempfile.mkdtemp(prefix=classname + '_',
                                       suffix='tmpdir',
                                       dir=self.parent_subtest.tmpdir)

    @classmethod
    def make_name(cls, parent_name):
        """
        Return automated sub-subtest name (config_section) based on parent_name

        :param parent_name: Unique name (config_section) of parent subtest
        :return:  String of unique subsubtest (config_section) name for class
        """
        return os.path.join(parent_name, cls.__name__)

    @classmethod
    def make_config(cls, all_configs, parent_config, name):
        """
        Form subsubtest configuration by inheriting parent subtest config
        """
        subsubtest_config = all_configs.get(name, {})
        # don't redefine the module
        _config = copy.deepcopy(parent_config)  # a copy
        # global defaults mixed in, even if overridden in parent :(
        for key, val in subsubtest_config.items():
            if key in all_configs['DEFAULTS']:
                def_val = all_configs['DEFAULTS'][key]
                par_val = parent_config[key]
                if val == def_val:
                    if par_val != def_val:
                        # Parent overrides default, subsubtest inherited
                        # default
                        _config[key] = par_val
                    else:
                        # Parent uses default, subsubtest did not override
                        _config[key] = def_val
                else:
                    _config[key] = val
            else:
                _config[key] = val
        return _config

    def make_subsubtest_config(self, all_configs, parent_config,
                               subsubtest_config):
        """
        Deprecated, use make_config() instead, will be removed soon
        """
        del subsubtest_config  # not used
        logging.warning("SubSubtest.make_subsubtest_config() is deprecated!")
        self.config = self.make_config(all_configs, parent_config,
                                       self.config_section)


class SubSubtestCaller(Subtest):

    r"""
    Extends Subtest by automatically discovering and calling child subsubtests.

    Child subsubtest methods ``initialize``, ``run_once``, and ``postprocess``,
    are executed together, for each subsubtest.  Whether or not any exception
    is raised, the ``cleanup`` method will always be called last.  The
    subsubtest the order is specified by the  ``subsubtests`` (CSV) config.
    option.  Child subsubtest configuration section is formed by appending the
    child's subclass name onto the parent's ``config_section`` value.  Parent
    configuration is passed to subsubtest, with the subsubtest's section
    overriding values with the same option name.
    """

    #: A list holding the ordered names of each subsubtest to load and run.
    #: (read-only).
    subsubtest_names = None

    #: A dictionary of subsubtest names to instances loaded (read-only), used
    #: for comparison during ``postprocess()`` against ``final_subtests`` to
    #: determine overall subtest success or failure.
    start_subsubtests = None

    #: The set of subsubtests which successfully completed all stages w/o
    #: exceptions.  Compared against ``start_subsubtests``. (read-only)
    final_subsubtests = None

    #: Dictionary containing exc_info, error_source data for a subsubtest
    #: for logging/debugging purposes while calling methods.  (read-only)
    exception_info = None

    def __init__(self, *args, **dargs):
        super(SubSubtestCaller, self).__init__(*args, **dargs)
        #: Need separate private dict similar to `sub_stuff` but different name

        self.subsubtest_names = []
        self.start_subsubtests = {}
        self.final_subsubtests = set()
        self.exception_info = {}

    def initialize(self):
        """
        Perform initialization steps needed before loading subsubtests.  Split
        up the ``subsubtests`` config. option by commas, into instance
        attribute ``subsubtest_names`` (list).
        """
        super(SubSubtestCaller, self).initialize()
        # Private to this instance, outside of __init__
        if self.config.get('subsubtests') is None:
            raise DockerTestNAError("Missing|empty 'subsubtests' in config.")
        sst_names = self.config['subsubtests']
        self.subsubtest_names = config.get_as_list(sst_names)

    def try_all_stages(self, name, subsubtest):
        """
        Attempt to execute each subsubtest stage (``initialize``, ``run_once``,
        and ``postprocess``).  For those that don't raise any exceptions,
        record subsubtest name in ``final_subsubtests`` set instance
        attribute. Hides _all_ ``AutotestError`` subclasses but logs traceback.

        :param name:  String, name of subsubtest class (and possibly module)
        :param subsubtest:  Instance of subsubtest or subclass
        """
        try:
            self.call_subsubtest_method(subsubtest.initialize)
            self.call_subsubtest_method(subsubtest.run_once)
            self.call_subsubtest_method(subsubtest.postprocess)
            # No exceptions, contribute to subtest success
            self.final_subsubtests.add(name)
        except AutotestError, detail:
            self.logtraceback(name,
                              self.exception_info["exc_info"],
                              self.exception_info["error_source"],
                              detail)
        except Exception, detail:
            self.logtraceback(name,
                              self.exception_info["exc_info"],
                              self.exception_info["error_source"],
                              detail)
            exc_info = self.exception_info["exc_info"]
            # cleanup() will still be called before this propigates
            raise exc_info[0], exc_info[1], exc_info[2]

    def run_all_stages(self, name, subsubtest):
        """
        Catch any exceptions coming from any subsubtest's stage to ensure
        it's ``cleanup()`` always runs.  Updates ``start_subsubtests``
        attribute with subsubtest names and instance to successfully
        loaded/imported.

        :param name:  String, name of subsubtest class (and possibly module)
        :param subsubtest:  Instance of subsubtest or subclass
        :raise DockerTestError: On subsubtest ``cleanup()`` failures **only**
        """
        if subsubtest is not None:
            # Guarantee cleanup() runs even if autotest exception
            self.start_subsubtests[name] = subsubtest
            try:
                self.try_all_stages(name, subsubtest)
            finally:
                try:
                    subsubtest.cleanup()
                except Exception, detail:
                    self.logtraceback(name,
                                      sys.exc_info(),
                                      "Cleanup",
                                      detail)
                    raise TestError("Sub-subtest %s cleanup"
                                    " failures: %s" % (name, detail))
        else:
            pass  # Assume a message was already logged

    def run_once(self):
        """
        Find, instantiate, and call all testing methods on each subsubtest, in
        order, subsubtest by subsubtest.  Autotest-specific exceptions are
        logged but non-fatal.  All other exceptions raised after calling
        subsubtest's ``cleanup()`` method.  Subsubtests which successfully
        execute all stages are appended to the ``final_subsubtests`` set
        (instance attribute) to determine overall subtest success/failure.
        """
        super(SubSubtestCaller, self).run_once()
        for name in self.subsubtest_names:
            self.run_all_stages(name, self.new_subsubtest(name))
        if len(self.start_subsubtests) == 0:
            raise TestError("No sub-subtests configured to run "
                            "for subtest %s" % self.config_section)

    def postprocess(self):
        """
        Compare set of subsubtest name (keys) from ``start_subsubtests``
        to ``final_subsubtests`` set.

        :raise DockerTestFail: if ``start_subsubtests != final_subsubtests``
        """
        super(SubSubtestCaller, self).postprocess()
        # Dictionary is overkill for pass/fail determination
        start_subsubtests = set(self.start_subsubtests.keys())
        failed_tests = start_subsubtests - self.final_subsubtests

        if failed_tests:
            raise DockerTestFail('Sub-subtest failures: %s' %
                                 str(failed_tests))

    def call_subsubtest_method(self, method):
        """
        Call ``method``, recording execution info. on exception.
        """
        try:
            method()
        except Exception:
            # Log problem, don't add to run_subsubtests
            self.exception_info["error_source"] = method.func_name
            self.exception_info["exc_info"] = sys.exc_info()
            raise

    @staticmethod
    def import_if_not_loaded(name, pkg_path):
        """
        Import module only if module is not loaded.
        """
        # Safe because test is running in a separate process from main test
        if name not in sys.modules:
            mod = imp.load_module(name, *imp.find_module(name, pkg_path))
            sys.modules[name] = mod
            return mod
        else:
            return sys.modules[name]

    def subsubtests_in_list(self, subsubtests, thinglist):
        """
        Return True if any subsubtest appears in thinglist
        """
        parent_name = self.config_section
        for subsub in [os.path.join(parent_name, subsub.strip())
                       for subsub in subsubtests]:
            if subsub in thinglist:
                return True
        return False

    def subsub_control_enabled(self, name, control_config):
        """
        Return True if name not excluded in control.ini
        """
        subthings_csv = control_config.get('subthings', '')
        exclude_csv = control_config.get('exclude', '')
        include_csv = control_config.get('include', '')
        if subthings_csv != '':
            subthings = [subthing.strip()
                         for subthing in subthings_csv.strip().split(',')]
        else:
            return False  # nothing is suppose to run?!?!?!?!?
        if exclude_csv != '':
            excludes = [exclude.strip()
                        for exclude in exclude_csv.strip().split(',')]
            if name in excludes:
                return False
            # else more checking reqired
        else:
            excludes = []  # exclude nothing
        if include_csv != '':
            includes = [include.strip()
                        for include in include_csv.strip().split(',')]
            # Can't use self.config['subsubtests'] b/c initialize() could
            # have modified/augmented it.
            specifics = self.subsubtests_in_list(self.subsubtest_names,
                                                 includes)
            if specifics:
                return name in includes
        else:
            # All self.subsubtest_names included if none appear
            pass
        # everything included, name not excluded, specific sub-subtests?
        specifics = self.subsubtests_in_list(self.subsubtest_names,
                                             subthings)
        if specifics:
            return name in subthings
        else:
            # This code is running, assume all sub-subtest should run.
            return True

    def subsub_enabled(self, subsubtest_class):
        """
        Determine if a subsubtest is enabled (default) or not (optional)

        :param subsubtest_class:  A SubSubtest class or sub-class.
        :return: False if subsubtest_class is explicitly disabled
        """
        if not issubclass(subsubtest_class, SubSubtest):
            raise ValueError("Object '%s' is not a SubSubtest class or "
                             "subclass" % str(subsubtest_class))
        sstc = subsubtest_class  # save some typing
        # subsubtest name
        name = sstc.make_name(self.config_section).strip()  # classmethod
        all_configs = config.Config()  # fast, cached in module
        parent_config = self.config
        if name not in all_configs:
            subsubtest_config = copy.deepcopy(parent_config)
        else:
            subsubtest_config = sstc.make_config(all_configs,
                                                 parent_config,
                                                 name)
        if not self.not_disabled(subsubtest_config, name):
            self.logdebug("Sub-subtest %s in 'disable' list in config.",
                          name)
            return False  # subsubtest in disabled option CSV list

        # Also check optional reference control.ini
        control_config = self.control_config
        if control_config != {}:
            return self.subsub_control_enabled(name, control_config)
        return True  # Empty or non-existant optional value, assume inclusion

    def new_subsubtest(self, name):
        """
        Attempt to import named subsubtest subclass from subtest module or
        module name.

        :param name: Class name, optionally external module-file name.
        :return: ``SubSubtest`` instance or ``None`` if failed to load
        """
        # Try in external module-file named 'name' also
        mydir = self.bindir
        # Look in module holding this subclass for subsubtest class first.
        myname = self.__class__.__name__
        mod = self.import_if_not_loaded(myname, [mydir])
        cls = getattr(mod, name, None)
        # Not found in this module, look in external module file with same name
        if cls is None:
            mod = self.import_if_not_loaded(name, [mydir])
            cls = getattr(mod, name, None)
        if issubclass(cls, SubSubtest):
            # Don't load excluded sub-subtests
            name = cls.make_name(self.config_section)
            if not self.subsub_enabled(cls):
                self.loginfo("Disabled/Excluded: '%s'", name)
                return None
            self.logdebug("Instantiating sub-subtest: %s", name)
            # Create instance, pass this subtest subclass as only parameter
            try:
                return cls(self)
            except DockerSubSubtestNAError, xcpt:
                self.logwarning(str(xcpt))
                # return None
        # Load failure will be caught and loged later
        return None

    def cleanup(self):
        super(SubSubtestCaller, self).cleanup()


class SubSubtestCallerSimultaneous(SubSubtestCaller):

    r"""
    Variation on SubSubtestCaller that calls test methods in subsubtest order.

    Child subsubtest methods ``initialize``, ``run_once``, and ``postprocess``,
    are executed separately, for each subsubtest.  Whether or not any exception
    is raised, the ``cleanup`` method will always be called last.  The
    subsubtest the order is specified by the  ``subsubtests`` (CSV) config.
    option.  Child subsubtest configuration section is formed by appending the
    child's subclass name onto the parent's ``config_section`` value.  Parent
    configuration is passed to subsubtest, with the subsubtest's section
    overriding values with the same option name.

    :param \*args: Passed through to super-class.
    :param \*\*dargs: Passed through to super-class.
    """

    #: Dictionary of subsubtests names to instances which successfully
    #: executed ``initialize()`` w/o raising exception
    run_subsubtests = None

    #: Dictionary of subsubtests names to instances which successfully
    #: executed ``run_once()`` w/o raising exception
    post_subsubtests = None

    def __init__(self, *args, **dargs):
        super(SubSubtestCallerSimultaneous, self).__init__(*args, **dargs)
        self.run_subsubtests = {}
        self.post_subsubtests = {}

    def initialize(self):
        super(SubSubtestCallerSimultaneous, self).initialize()
        for name in self.subsubtest_names:
            subsubtest = self.new_subsubtest(name)
            if subsubtest is not None:
                # Guarantee it's cleanup() runs
                self.start_subsubtests[name] = subsubtest
                try:
                    subsubtest.initialize()
                    # Allow run_once() on this subsubtest
                    self.run_subsubtests[name] = subsubtest
                except AutotestError, detail:
                    # Log problem, don't add to run_subsubtests
                    self.logtraceback(name, sys.exc_info(), "initialize",
                                      detail)
        if len(self.start_subsubtests) == 0:
            raise TestError("No sub-subtests configured to run "
                            "for subtest %s", self.config_section)

    def run_once(self):
        # DO NOT CALL superclass run_once() this variation works
        # completely differently!
        for name, subsubtest in self.run_subsubtests.items():
            try:
                subsubtest.run_once()
                # Allow postprocess()
                self.post_subsubtests[name] = subsubtest
            except AutotestError, detail:
                # Log problem, don't add to post_subsubtests
                self.logtraceback(name, sys.exc_info(), "run_once", detail)

    def postprocess(self):
        # DO NOT CALL superclass run_once() this variation works
        # completely differently!
        start_subsubtests = set(self.start_subsubtests.keys())
        final_subsubtests = set()
        for name, subsubtest in self.post_subsubtests.items():
            try:
                subsubtest.postprocess()
                # Will form "passed" set
                final_subsubtests.add(name)
            except AutotestError, detail:
                # Forms "failed" set by exclusion from final_subsubtests
                self.logtraceback(name, sys.exc_info(), "postprocess",
                                  detail)
        if not final_subsubtests == start_subsubtests:
            raise DockerTestFail('Sub-subtest failures: %s'
                                 % str(start_subsubtests - final_subsubtests))

    def cleanup(self):
        super(SubSubtestCallerSimultaneous, self).cleanup()
        cleanup_failures = set()  # just for logging purposes
        for name, subsubtest in self.start_subsubtests.items():
            try:
                subsubtest.cleanup()
            except AutotestError, detail:
                cleanup_failures.add(name)
                self.logtraceback(name, sys.exc_info(), "cleanup",
                                  detail)
        if len(cleanup_failures) > 0:
            raise DockerTestError("Sub-subtest cleanup failures: %s"
                                  % cleanup_failures)
