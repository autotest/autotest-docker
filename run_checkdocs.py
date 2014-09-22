#!/usr/bin/env python
"""
Verifies that subtests.rst contains all required data
"""
import os
import re
import sys
from dockertest.environment import SubtestDocs


# TODO: Subclass environment.AllGoodBase to seperate behavior from results
class SubtestsDocumented(object):
    """
    Checker object
    """
    def __init__(self, path='.'):
        """ Location of the subtests.rst directory """
        self.path = os.path.join(path, 'subtests')
        try:
            self.doc = open(os.path.join(path, 'subtests.rst')).read()
        except IOError:
            print "No subtests.rst file found, perhaps you need to run make"
            sys.exit(-1)

    def check(self):
        """ Check the subtests tree """
        err, dir_tests = self.walk_directories()
        err |= self.check_missing_tests(dir_tests)
        return err

    def walk_directories(self):
        """ Checks whether all existing tests are documented """
        dir_tests = SubtestDocs.filenames()
        err = False
        for dir_item in dir_tests:
            name = SubtestDocs.name(dir_item)
            if name:
                # Require at least the same number of `=` as chapter name
                chapter = "``%s`` Subtest\n" % name
                chapter += "=" * (len(chapter) - 1)
                if chapter not in self.doc:
                    err = True
                    if name in self.doc:
                        print ("%s present in subtests.rst, but not as \n%s."
                               % (name, chapter))
                    else:
                        print "%s not present in subtests.rst" % name
        return err, dir_tests

    def check_missing_tests(self, dir_tests):
        """ Checks missing tests """
        doc_tests = set(re.findall(r'``([^`\n]+)`` Sub-test\n===', self.doc))
        missing = doc_tests.difference(dir_tests)
        if missing:
            print ("%s tests are documented, but not present in the file "
                   "structure." % ", ".join(missing))
            return True
        return False


if __name__ == "__main__":
    STATUS = SubtestsDocumented().check()
    if STATUS:
        sys.exit(-1)
