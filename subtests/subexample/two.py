"""
Sub-subtests can appear in separate modules also
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest.subtest import SubSubtest

class two(SubSubtest):
    """
    Minimal Subtest-like class, doesn't define all test.test methods
    """

    def run_once(self):
        """
        Called to run test
        """
        super(two, self).run_once() # Prints out basic info
        self.parentSubtest.special_function(", or don't use it if not needed")
