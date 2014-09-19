#!/usr/bin/env python
"""
Verifies that index.rst contains all required data
"""
import os
import re
import sys


class SubtestsDocumented(object):
    """
    Checker object
    """
    def __init__(self, path='.'):
        """ Location of the index.rst directory """
        self.path = os.path.join(path, 'subtests')
        self.doc = open(os.path.join(path, 'index.rst')).read()

    def check(self):
        """ Check the subtests tree """
        err, dir_tests = self.walk_directories()
        err |= self.check_missing_tests(dir_tests)
        return err

    def walk_directories(self):
        """ Checks whether all existing tests are documented """
        def test_name(dir_item):
            """ return test_name if dir is test, otherwise return None """
            path, _, files = dir_item
            # directory and main test share the same name
            if os.path.basename(path) + '.py' not in files:
                return None
            return os.path.relpath(path, self.path)

        dir_tests = []
        err = False
        for dir_item in os.walk(self.path):
            name = test_name(dir_item)
            if name:
                dir_tests.append(name)
                # Require at least the same number of `=` as chapter name
                chapter = "``%s`` Sub-test\n" % name
                chapter += "=" * (len(chapter) - 1)
                if chapter not in self.doc:
                    err = True
                    if name in self.doc:
                        print ("%s present in index.rst, but not as \n%s."
                               % (name, chapter))
                    else:
                        print "%s not present in index.rst" % name
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
