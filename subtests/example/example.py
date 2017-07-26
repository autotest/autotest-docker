r"""
Summary
---------

Textual description of *what* this subtest and/or sub-subtests
will exercize in general terms.  The next section describes the
general operations that will be performed (i.e. **how** they
will be tested).

Operational Summary
----------------------

#. Summary of step one
#. Summary of step two
#. Summary of step three

Operational Detail
--------------------

Example test, nothing detailed about it.

Prerequisites
---------------

This example test does not require anything other than
Autotest, Docker autotest, and this file.
"""

from dockertest import subtest


class example(subtest.Subtest):
    iterations = 3
    config_section = 'example'
    stuff = None  # Will turn into empty dictionary, store private data here

    def initialize(self):
        """
        Called every time the test is run, first thing.
        """
        super(example, self).initialize()  # Prints out basic info
        # Do Something useful here, store run_once input in 'stuff'
        self.stuff['sample_key'] = 'a'

    def setup(self):
        """
        Called once per version change, after initialize()
        """
        super(example, self).setup()  # Prints out basic info
        # Do Something useful here
        self.stuff['something_else'] = 'b'

    def run_once(self):
        """
        Called to run test, after initialize/setup
        """
        super(example, self).run_once()  # Prints out basic info
        # Do Something useful here, store results in 'stuff'
        self.stuff['dc'] = 'DockerCmd(...)'

    def postprocess_iteration(self):
        """
        Called to process each iteration of run_once()
        """
        super(example, self).postprocess_iteration()  # Prints out basic info
        # Do Something useful here, check 'stuff' for iteration-errors
        self.stuff['postprocess_iteration'] = 'nobody ever uses this'

    def postprocess(self):
        """
        Called to process all results after all postprocess_iteration()'s
        """
        super(example, self).postprocess()  # Prints out basic info
        # Do Something useful here, check 'stuff' for overall errors
        self.stuff['postprocess'] = 'this is where you check results'

    def cleanup(self):
        """
        Always called, after all other methods
        """
        super(example, self).cleanup()  # Prints out basic info
        # Do Something useful here, leave environment as we received it
        self.stuff['cleanup'] = 'blah blah'
