"""
Call superclass during each stage
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

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

    def setup(self):
        """
        Called once per version change, after initialize()
        """
        super(example, self).setup()  # Prints out basic info
        # Do Something useful here

    def run_once(self):
        """
        Called to run test, after initialize/setup
        """
        super(example, self).run_once()  # Prints out basic info
        # Do Something useful here, store results in 'stuff'

    def postprocess_iteration(self):
        """
        Called to process each iteration of run_once()
        """
        super(example, self).postprocess_iteration()  # Prints out basic info
        # Do Something useful here, check 'stuff' for iteration-errors

    def postprocess(self):
        """
        Called to process all results after all postprocess_iteration()'s
        """
        super(example, self).postprocess()  # Prints out basic info
        # Do Something useful here, check 'stuff' for overall errors

    def cleanup(self):
        """
        Always called, after all other methods
        """
        super(example, self).cleanup()  # Prints out basic info
        # Do Something useful here, leave environment as we received it
