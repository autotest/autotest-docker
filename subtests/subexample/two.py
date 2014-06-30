"""
Sub-subtests can appear in separate modules also
"""

from dockertest.subtest import SubSubtest


class two(SubSubtest):

    """
    Minimal Subtest-like class, doesn't define all test.test methods
    """

    def run_once(self):
        """
        Called to run test
        """
        super(two, self).run_once()  # Prints out basic info
        self.parent_subtest.special_function(", or don't use it if not needed")
