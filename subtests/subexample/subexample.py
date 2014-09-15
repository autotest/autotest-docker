r"""
Textual description of *what* this subtest and/or sub-subtests
will exercize in general terms.  The next section describes the
general operations that will be performed (i.e. **how** they
will be tested).

Operational Summary
----------------------

Test One:
#. Summary of step one
#. Summary of step two
#. Summary of step three

Test Two:
#. Summary of step one
#. Summary of step two

Prerequisites
---------------

*  This example test does not require anything other than
   Autotest, Docker autotest, and this file.

Configuration
---------------

General:
*  The optional ``iterations`` option specifies how many times
   this test will run.  The current iteration number is available
   in the ``iteration`` attribute.

Test Two:
*  Doesn't do anything differently, so configuration is the same.

Test Three:
*  No additional configuation
"""

import logging
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller


class subexample(SubSubtestCaller):

    def initialize(self):
        """
        Called before ``setup()`` method
        """
        super(subexample, self).initialize()
        self.stuff = "Store whatever subtest private stuff here"

    def special_function(self, extra_msg):
        """
        Define subtest-wide shared methods here
        """
        self.loginfo(self.stuff + extra_msg)


class one(SubSubtest):

    def initialize(self):
        """
        Called every time the test is run.
        """
        super(one, self).initialize()  # Prints out basic info
        self.logdebug("debug console logging works in sub-subtests")
        # Keep track of whatever you like here
        self.sub_stuff = ", and sub-subtest private stuff here"
        # Do Something useful here, store run_once input in 'stuff'

    def run_once(self):
        """
        Called to run test
        """
        super(one, self).run_once()  # Prints out basic info
        # Use parent subtest instance as needed
        self.parent_subtest.special_function(self.sub_stuff)
        # Do Something useful here, store results in 'stuff'

    def postprocess(self):
        """
        Called to process results
        """
        super(one, self).postprocess()  # Prints out basic info
        self.failif(False, "Sub-subtest can use failif too!")
        # Do Something useful here, check 'stuff' for overall errors

    def cleanup(self):
        """
        Always Called, after all other methods
        """
        super(one, self).cleanup()  # Prints out basic info
        self.loginfo("This message appears on console only")
        logging.info("Official test log update, this sub-subtest is done!")
        # Do Something useful here, leave environment as we received it
