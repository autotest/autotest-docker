"""
Generic test.test derivative
"""

import logging
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
        self.config = config.Config()[self.config_section]

    # Private workaround due to job/test instance private attributes/methods :(
    def _log(self, level, message, *args):
        method = getattr(logging, level)
        message = '%s: %s' % (level.upper(), message)
        sle = base_job.status_log_entry("RUNNING", None, message, '', {})
        rendered = self._re(sle)
        return method(rendered, *args)

    # These methods can optionally be overridden by subclasses

    def execute(self, *args, **dargs):
        """**Do not override**, needed to pull data from super class"""
        super(Subtest, self).execute(iterations=self.iterations,
                                     *args, **dargs)

    def setup(self):
        """
        Called once per version change
        """
        self.loginfo("setup() for subtest version %s",
                     version.int2str(self.version))
        # TODO: Add helpers for subtests to call in setup() that
        # TODO: check testing-prerequsits.  For example, build test
        # TODO: could verify Docker file exists, import test
        # TODO: could check the 'tar' command exists, etc.

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
        """
        Log a DEBUG level message to the controlling terminal **only**

        :param message: Same as logging.debug()
        :*args: Same as logging.debug()
        """
        return self._log('debug', message, *args)

    def loginfo(self, message, *args):
        """
        Log a INFO level message to the controlling terminal **only**

        :param message: Same as logging.info()
        :*args: Same as logging.info()
        """
        return self._log('info', message, *args)

    def logwarning(self, message, *args):
        """
        Log a WARNING level message to the controlling terminal **only**

        :param message: Same as logging.warning()
        :*args: Same as logging.warning()
        """
        return self._log('warning', message, *args)

    def logerror(self, message, *args):
        """
        Log a ERROR level message to the controlling terminal **only**

        :param message: Same as logging.error()
        :*args: Same as logging.error()
        """
        return self._log('error', message, *args)
