"""
Adapt/extend autotest.client.test.test for Docker test sub-framework

This module provides two helper classes intended to make writing
subtests easier.  They hide some of the autotest ``test.test``
complexity, while providing some helper methods for logging
output to the controling terminal (only) and automatically
loading the specified configuration section (see `configuration module`_)
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import logging
import tempfile
import os.path
import imp
from autotest.client.shared import error, base_job
from autotest.client import job, test
import version, config


class Subtest(test.test):
    """
    Extends autotest test.test with dockertest-specific items
    """
    #: Version number from configuration, read-only / setup inside __init__
    #: affects one-time building of bundled content in 'self.srcdir' by
    #: controlling the call to setup() method only when it chanes.  Compared
    #: to dockertest API, when specified in configuration.  Test will not
    #: execute if there is a MAJOR/MINOR mismatch (revision is okay).
    version = None
    #: The current iteration being run, read-only / set by the harness.
    iteration = None  # set from test.test
    #: The number of iterations to run in total, override this in subclass.
    iterations = 1
    #: Configuration section used for subclass, read-only / set by Subtest class
    config_section = 'DEFAULTS'
    #: Private namespace for use by subclasses **ONLY**.  This attribute
    #: is completely ignored everywhere inside the dockertest API.  Subtests
    #: are encourraged to use it for temporarily storing results/info. for
    #: internal subclass-use.
    stuff = None
    #: private method used by log*() methods internally, do not use.
    _re = None

    def __init__(self, *args, **dargs):
        """
        Initialize new subtest, passes all arguments through to parent class
        """
        super(Subtest, self).__init__(*args, **dargs)
        # log indentation level not easy to get at, so use opaque implementation
        _si = job.status_indenter(self.job)
        _sl = base_job.status_logger(self.job, _si)
        self._re = _sl.render_entry  # will return string w/ proper indentation
        # So tests don't need to set this up every time
        config_parser = config.Config()
        self.config = config_parser.get(self.config_section)
        if self.config is None:
            logging.warning("No configuration section found '%s'",
                            self.config_section)
            self.config = config_parser['DEFAULTS']
            # Mark this to not be checked, no config, no version info.
            self.config['config_version'] = version.NOVERSIONCHECK
            self.version = 0
        else:
            # Version number used by one-time setup() test.test method
            self.version = version.str2int(self.config['config_version'])
        # Fail test if configuration being used doesn't match dockertest API
        version.check_version(self.config)
        # Log original key/values before subtest could modify them
        self.write_test_keyval(self.config)
        # Optionally setup different iterations if option exists
        self.iterations = self.config.get('iterations', self.iterations)
        # subclasses can do whatever they like with this
        self.stuff = {}

    # Private workaround due to job/test instance private attributes/methods :(
    def _log(self, level, message, *args):
        method = getattr(logging, level)
        message = '%s: %s' % (level.upper(), message)
        sle = base_job.status_log_entry("RUNNING", None, None, message, {})
        rendered = self._re(sle)
        return method(rendered, *args)

    # These methods can optionally be overridden by subclasses

    def execute(self, *args, **dargs):
        """**Do not override**, needed to pull data from super class"""
        #self.job.add_sysinfo_command("", logfile="lspci.txt")
        super(Subtest, self).execute(iterations=self.iterations,
                                     *args, **dargs)

    def setup(self):
        """
        Called once per version change
        """
        self.loginfo("setup() for subtest version %s", self.version)

    def initialize(self):
        """
        Called every time the test is run.
        """
        self.loginfo("initialize()")

    def run_once(self):
        """
        Called to run test for each iteration
        """
        self.loginfo("run_once() iteration %d of %d",
                     self.iteration, self.iterations)

    def postprocess_iteration(self):
        """
        Called for each iteration, used to process results
        """
        self.loginfo("postprocess_iteration(), iteration #%d",
                      self.iteration)

    def postprocess(self):
        """
        Called after all postprocess_iteration()'s, processes all results
        """
        self.loginfo("postprocess()")

    def cleanup(self):
        """
        Called after all other methods, even if exception is raised.
        """
        self.loginfo("cleanup()")

    # Some convenience methods for tests to use

    @staticmethod
    def failif(condition, reason):
        """
        Convenience method for subtests to avoid importing TestFail exception

        :param condition: Boolean condition, fail test if True.
        :param reason: Helpful text describing why the test failed
        """
        if bool(condition):
            raise error.TestFail(reason)

    def logdebug(self, message, *args):
        r"""
        Log a DEBUG level message to the controlling terminal **only**

        :param message: Same as logging.debug()
        :\*args: Same as logging.debug()
        """
        return self._log('debug', message, *args)

    def loginfo(self, message, *args):
        r"""
        Log a INFO level message to the controlling terminal **only**

        :param message: Same as logging.info()
        :\*args: Same as logging.info()
        """
        return self._log('info', message, *args)

    def logwarning(self, message, *args):
        r"""
        Log a WARNING level message to the controlling terminal **only**

        :param message: Same as logging.warning()
        :\*args: Same as logging.warning()
        """
        return self._log('warning', message, *args)

    def logerror(self, message, *args):
        r"""
        Log a ERROR level message to the controlling terminal **only**

        :param message: Same as logging.error()
        :\*args: Same as logging.error()
        """
        return self._log('error', message, *args)


class SubSubtest(object):
    """
    Simplistic/minimal subtest interface matched with config section

    *Note:* Contains, and is similar to, but DOES NOT represent
            the same interface as the Subtest class (above).
    """
    #: Reference to outer, parent test.  Read-only / set in __init__
    parentSubtest = None
    #: subsubsub test config instance, read-write, setup in __init__ but
    #: persists across iterations.  Handy for storing temporary results.
    config = None
    #: Path to a temporary directory which will automatically be
    #: removed during cleanup()
    tmpdir = None  # automatically determined in initialize()
    #: Private namespace for use by subclasses **ONLY**.  This attribute
    #: is completely ignored everywhere inside the dockertest API.  Subtests
    #: are encourraged to use it for temporarily storing results/info. for
    #: internal subclass-use.
    subStuff = None

    def __init__(self, parent_subtest):
        """
        Initialize sub-subtest

        :param parentSubtest: The Subtest instance calling this instance
        """
        # Allow parent_subtest to use any interface this
        # class is setup to support. Don't check type.
        self.parentSubtest = parent_subtest
        # Append this subclass's name onto parent's section name
        # e.g. [parent_config_section/child_class_name]
        config_section = (os.path.join(self.parentSubtest.config_section,
                                       self.__class__.__name__))
        # Allow child to inherit but also override parent config
        self.config = self.parentSubtest.config.copy()
        self.config.update(config.Config()[config_section])
        self.config['subsubtest_config_section'] = config_section
        # Not automatically logged along with parent subtest
        # for records/archival/logging purposes
        note = {'Configuration_for_Subsubtest':config_section}
        self.parentSubtest.write_test_keyval(note)
        self.parentSubtest.write_test_keyval(self.config)
        # subclasses can do whatever they like with this
        self.subStuff = {}

    def initialize(self):
        """
        Called every time the test is run.
        """
        self.parentSubtest.loginfo("%s initialize()", self.__class__.__name__)
        self.tmpdir = tempfile.mkdtemp(prefix=self.__class__.__name__,
                                       suffix='tmp',
                                       dir=self.parentSubtest.tmpdir)

    def run_once(self):
        """
        Called once only to exercize subject of sub-subtest
        """
        self.parentSubtest.loginfo("%s run_once()", self.__class__.__name__)

    def postprocess(self):
        """
        Called to process results of subject
        """
        self.parentSubtest.loginfo("%s postprocess()", self.__class__.__name__)

    def cleanup(self):
        """
        Always called, even dispite any exceptions thrown.
        """
        self.parentSubtest.loginfo("%s cleanup()", self.__class__.__name__)
        # tmpdir is cleaned up automatically by harness

    def make_repo_name(self):
        """
        Convenience function to generate a unique test-repo name
        """
        prefix = self.parentSubtest.config['repo_name_prefix']
        name = os.path.basename(self.tmpdir)
        postfix = self.parentSubtest.config['repo_name_postfix']
        return "%s%s%s" % (prefix, name, postfix)

    # Handy to have here also
    failif = staticmethod(Subtest.failif)
    def logdebug(self, message, *args):
        """
        Same as Subtest.logdebug
        """
        newmsg = 'SubSubtest %s DEBUG: %s' % (self.__class__.__name__, message)
        return self.parentSubtest.logdebug(newmsg, *args)

    def loginfo(self, message, *args):
        """
        Same as Subtest.loginfo
        """
        newmsg = 'SubSubtest %s INFO: %s' % (self.__class__.__name__, message)
        return self.parentSubtest.loginfo(newmsg, *args)

    def logwarning(self, message, *args):
        """
        Same as Subtest.logwarning
        """
        newmsg = 'SubSubtest %s WARN: %s' % (self.__class__.__name__, message)
        return self.parentSubtest.logwarning(newmsg, *args)

    def logerror(self, message, *args):
        """
        Same as Subtest.logerror
        """
        newmsg = 'SubSubtest %s ERROR: %s' % (self.__class__.__name__, message)
        return self.parentSubtest.logerror(newmsg, *args)


class SubSubtestCaller(Subtest):
    """
    Extends Subtest by automatically discovering and calling child subsubtests.

    Child subsubtests are execute in the order specified by the
    ``subsubtests`` (CSV) configuration option.  Child subsubtest
    configuration section is formed by appending the child's subclass name
    onto the parent's ``config_section`` value.
    """

    #: In case subclasses want to hard-code a list of subtest names
    #: instead of getting them from config.
    subsubtests = None

    #: Private, internal-use, don't touch.  Sub-Subtest Caller Data
    _sscd = None

    def __init__(self, *args, **dargs):
        """
        Call subtest __init__ and setup local attributes

        :param \*args: Opaque, passed through to super-class
        :param \*\*dargs: Opaque, passed through to super-class
        """
        super(SubSubtestCaller, self).__init__(*args, **dargs)
        #: Need separate private dict similar to `subStuff` but different name
        self._sscd = {}

    def initialize(self):
        """
        Import and call initialize() on every subsubtest in 'subsubtests' option
        """
        super(SubSubtestCaller, self).initialize()
        # Private to this instance, outside of __init__
        start_subsubtests = self._sscd['start_subsubtests'] = {}
        run_subsubtests = self._sscd['run_subsubtests'] = {}
        subsubtest_names = None
        if self.subsubtests is None:
            subsubtest_names = self.config['subsubtests'].strip().split(",")
        else:
            subsubtest_names = [self.subsubtests]

        for name in subsubtest_names:
            subsubtest = self.new_subsubtest(name)
            if subsubtest is not None:
                # Guarantee it's cleanup() runs
                start_subsubtests[name] = subsubtest
                try:
                    subsubtest.initialize()
                    # Allow run_once()
                    run_subsubtests[name] = subsubtest
                except error.AutotestError, detail:
                    # Log problem, don't add to run_subsubtests
                    self.logerror("%s failed to initialize: %s: %s", name,
                                  detail.__class__.__name__, detail)

    def run_once(self):
        """
        Call successfully imported subsubtest's run_once() method
        """
        super(SubSubtestCaller, self).run_once()
        post_subsubtests = self._sscd['post_subsubtests'] = {}
        for name, subsubtest in self._sscd['run_subsubtests'].items():
            try:
                subsubtest.run_once()
                # Allow postprocess()
                post_subsubtests[name] = subsubtest
            except error.AutotestError, detail:
                # Log problem, don't add to post_subsubtests
                self.loginfo("%s failed in run_once: %s: %s", name,
                             detail.__class__.__name__, detail)

    def postprocess(self):
        """
        Call all subsubtest's postprocess() method that completed run_once()
        """
        super(SubSubtestCaller, self).postprocess()
        # Dictionary is overkill for pass/fail determination
        start_subsubtests = set(self._sscd['start_subsubtests'].keys())
        final_subsubtests = set()
        for name, subsubtest in self._sscd['post_subsubtests'].items():
            try:
                subsubtest.postprocess()
                # Will form "passed" set
                final_subsubtests.add(name)
            # Fixme: How can this be avoided, yet guarantee cleanup() and
            #        postprocess for other subtests?
            except error.AutotestError, detail:
                # Forms "failed" set by exclusion, but log problem
                self.loginfo("%s failed in postprocess: %s: %s", name,
                             detail.__class__.__name__, detail)
        if not final_subsubtests == start_subsubtests:
            raise error.TestFail('Sub-subtest failures: %s'
                                 % str(start_subsubtests - final_subsubtests))

    def cleanup(self):
        """
        Call successfully imported subsubtest's cleanup() method
        """
        super(SubSubtestCaller, self).cleanup()
        cleanup_failures = set()
        for name, subsubtest in self._sscd['start_subsubtests'].items():
            try:
                subsubtest.cleanup()
            except error.AutotestError, detail:
                cleanup_failures.add(name)
                self.logerror("%s failed to cleanup: %s: %s", name,
                              detail.__class__.__name__, detail)
        if len(cleanup_failures) > 0:
            raise error.TestError("Sub-subtest cleanup failures: %s"
                                   % cleanup_failures)

    def new_subsubtest(self, name):
        """
        Attempt to import named subsubtest subclass from module name in this dir
        """
        mydir = self.bindir
        mod = imp.load_module(name, *imp.find_module(name, [mydir]))
        cls = getattr(mod, name, None)
        if callable(cls):
            return cls(self)
        self.logerror("Failed importing sub-subtest %s")
        return None
