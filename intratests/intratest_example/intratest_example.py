from dockertest import subtest


class intratest_example(subtest.Subtest):

    def run_once(self):
        """
        Called to run test, after initialize/setup
        """
        self.loginfo("This is %s.run_once() executing",
                     self.__class__.__name__)
