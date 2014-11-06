#!/usr/bin/env python
"""
Verify all subtests contain required minimum sections, ini's doc all options
"""
import os
import re
import sys
import docutils.nodes
from dockertest.documentation import SubtestDoc

# Parse rst docstring into doctree, store list of top-level section names
class SubtestDocSections(SubtestDoc):

    sections = None  # List of found section names
    # Make sure no configuration section is rendered
    ConfigDocClass = None
    NoINIString = '\n'

    def __init__(self, subtest_path):
        self.sections = []
        super(SubtestDocSections, self).__init__(subtest_path)


    def conv(self, input_string):

        class MinSecVisitor(docutils.nodes.SparseNodeVisitor):

            @staticmethod
            def visit_section(node):
                # self is attribute on SubtestDocSections!
                self.sections += node.get('names')  # maybe more than one name
                # Only care about top-level section-nodes
                node.parent.remove(node)
                # Don't visit children, don't call depart_section()
                raise docutils.nodes.SkipNode()

        self.rst2doctree(input_string, MinSecVisitor)
        self.sections.sort()
        return ','.join(self.sections)


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
        dir_tests = SubtestDoc.module_filenames()
        err = False
        for dir_item in dir_tests:
            name = SubtestDoc.name(dir_item)
            if 'example' in name:
                continue
            missing_sections = self.missing_sections(dir_item)
            if missing_sections is not None:
                err = True
                print ("%s: Missing '%s' section"
                       % (dir_item, missing_sections))
            extra_sections = self.extra_sections(dir_item)
            if extra_sections is not None:
                err = True
                print ("%s: Extra nonstandard '%s' section found"
                       % (dir_item, extra_sections))
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

    def missing_sections(self, subtest_path):
        """
        Return name of any missing required docstring sections

        :param subtest_path: Path to subtest module
        :return: None or name of missing required section
        """
        subtest_doc_sections = SubtestDocSections(subtest_path)
        # Output doesn't matter, only sections instance attr. value
        print subtest_path, str(subtest_doc_sections)
        for required in ('summary', 'operational summary'):
            if required not in subtest_doc_sections.sections:
                return required
        return None

    def extra_sections(self, subtest_path):
        subtest_doc_sections = SubtestDocSections(subtest_path)
        str(subtest_doc_sections)
        acceptable = ('prerequisites', 'operational detail',
                      'summary', 'operational summary')
        acceptable = set(acceptable)
        actual = set(subtest_doc_sections.sections)
        difference = actual - acceptable
        try:
            return difference.pop()
        except KeyError:
            return None

if __name__ == "__main__":
    STATUS = SubtestsDocumented().check()
    if STATUS:
        sys.exit(-1)
