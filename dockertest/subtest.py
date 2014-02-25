"""
Adapt/extend autotest.client.test.test for Docker test sub-framework

This module provides two helper classes intended to make writing
subtests easier.  They hide some of the autotest ``test.test``
complexity, while providing some helper methods for logging
output to the controling terminal (only) and automatically
loading the specified configuration section (see `configuration module`_)
"""

import logging, tempfile, os.path
from autotest.client.shared import error, base_job
from autotest.client import job, test
import version, config

class Subtest(test.test):
    """
    Extends autotest test.test with dockertest-specific items
    """
    #: Version number of the test, **not** related to the
    #: dockertest API or configuration version whatsoever.
    #: Instead, this version number is used by autotest
    #: for any test overriding Subtest.setup().  It ensures
    #: that the method is only executed once per version.
    version = None  # "x.y.z" string set by subclass
    #: The current iteration being run, read-only / set by the harness.
    iteration = None  # set from test.test
    #: The number of iterations to run in total, override this in subclass.
    iterations = 1
    #: Configuration section used for subclass, read-only / set by Subtest class
    config_section = 'DEFAULTS'

    _re = None  # private method used by log*() methods internally

    def __init__(self, *args, **dargs):
        """
        Initialize new subtest, passes all arguments through to parent class
        """
        # Version number required by one-time setup() test.test method
        if self.__class__.version is None:
            raise error.TestError("Test version number not provided")
        # Convert string-format version into shifty integer
        if isinstance(self.__class__.version, (str, unicode)):
            self.__class__.version = version.str2int(self.__class__.version)
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
        # Log original key/values before subtest could modify them
        self.write_test_keyval(self.config)
        # Optionally setup different iterations if option exists
        self.iterations = self.config.get('iterations', self.iterations)

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
        self.loginfo("setup() for subtest version %s",
                     version.int2str(self.version))

    def initialize(self):
        """
        Called every time the test is run.
        """
        self.loginfo("initialize()")
        # Fail test if configuration being used is too old
        version.check_version(self.config)

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


# Does not follow same subtest interface
class SubSubtest(object):
    """
    Simplistic/minimal subtest interface matched with config section
    """
    #: Reference to outer, parent test.  Read-only / set in __init__
    test = None
    #: subsubsub test config instance, read-write, setup in __init__ but
    #: persists across iterations.  Handy for storing temporary results.
    config = None
    #: Path to a temporary directory which will automatically be
    #: removed during cleanup()
    tmpdir = None  # automatically determined in initialize()

    def __init__(self, parent_test):
        """
        Initialize sub-subtest

        :param parent_test: The Subtest instance calling this instance
        """
        self.test = parent_test
        config_section = (os.path.join(self.test.config_section,
                                       self.__class__.__name__))
        self.config = config.Config()[config_section]
        self.config['subsubtest_config_section'] = config_section
        # Not automatically logged along with parent
        self.test.write_test_keyval(self.config)

    def initialize(self):
        """
        Called every time the test is run.
        """
        self.test.loginfo("%s initialize()", self.__class__.__name__)
        self.tmpdir = tempfile.mkdtemp(prefix=self.__class__.__name__,
                                       suffix='tmp',
                                       dir=self.test.tmpdir)

    def run_once(self):
        """
        Called once only to exercize subject of sub-subtest
        """
        self.test.loginfo("%s run_once()", self.__class__.__name__)

    def postprocess(self):
        """
        Called to process results of subject
        """
        self.test.loginfo("%s postprocess()", self.__class__.__name__)

    def cleanup(self):
        """
        Always called, even dispite any exceptions thrown.
        """
        self.test.loginfo("%s cleanup()", self.__class__.__name__)
        # tmpdir is cleaned up automatically by harness

    def make_repo_name(self):
        """
        Convenience function to generate a unique test-repo name
        """
        prefix = self.test.config['repo_name_prefix']
        name = os.path.basename(self.tmpdir)
        postfix = self.test.config['repo_name_postfix']
        return "%s%s%s" % (prefix, name, postfix)

    def logdebug(self, message, *args):
        """
        Same as Subtest.logdebug
        """
        message = '%s: %s' % (self.__class__.__name__,  message)
        return self.test.logdebug(message, *args)

    def loginfo(self, message, *args):
        """
        Same as Subtest.loginfo
        """
        message = '%s: %s' % (self.__class__.__name__,  message)
        return self.test.loginfo(message, *args)

    def logwarning(self, message, *args):
        """
        Same as Subtest.logwarning
        """
        message = '%s: %s' % (self.__class__.__name__,  message)
        return self.test.logwarning(message, *args)

    def logerror(self, message, *args):
        """
        Same as Subtest.logerror
        """
        message = '%s: %s' % (self.__class__.__name__,  message)
        return self.test.logerror(message, *args)
