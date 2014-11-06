#!/usr/bin/env python
"""
Verify all subtests contain required minimum sections, ini's doc all options
"""
import os
import re
import sys
import docutils.nodes
from dockertest.documentation import SubtestDoc
from dockertest.documentation import ConfigDoc
from dockertest.documentation import DefaultDoc
from dockertest.documentation import ConfigINIParser


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


# Access undocumented test configuration items from high-level interface
class UndocSubtestConfigItems(SubtestDoc):

    docitems = None  # Tuple of parsed ini option docs
    NoINIString = '\n'

    def __init__(self, subtest_path):
        self.docitems = tuple()
        self.defaults = DefaultDoc()
        super(UndocSubtestConfigItems, self).__init__(subtest_path)

    @property
    def ConfigDocClass(self):

        class ConfigDocCapture(ConfigDoc):

            # This _self is different from outer self on purpose.
            def conv(_self, input_string):
                # Copy parser state at final output stage
                self.docitems = _self.docitems
                return ''

        return ConfigDocCapture

    def conv(self, input_string):
        if not isinstance(self.docitems, ConfigINIParser):
            print ('Warning: No configuration found for: %s'
                   % SubtestDoc.name(self.subtest_path))
            return ''
        # Supplied by tuple-subclass
        undoc_option_doc = self.docitems.undoc_option_doc
        subtest_name = self.docitems.subtest_name
        get_default = self.defaults.get_default
        # Split options by subtest and subsubtests, filter along the way.
        subtest_options = []  # just option names for comparison
        subtest_docitems = []
        subsub_docitems = []
        for docitem in self.docitems:
            if get_default(docitem.option) is not None:
                continue  # skip default options
            if docitem.subthing == subtest_name:
                if docitem.option != 'subsubtests':  # special case
                    subtest_options.append(docitem.option)
                    subtest_docitems.append(docitem)
            else:  # must be non-default sub-subtest option
                subsub_docitems.append(docitem)
        # Remove all subsub docitem options appearing in subtest_options
        subsub_docitems = [docitem
                           for docitem in subsub_docitems
                           if docitem.option not in subtest_options]
        # Combine lists, remove all documented items
        docitems = [docitem
                    for docitem in subtest_docitems + subsub_docitems
                    if docitem.desc == undoc_option_doc]
        return ', '.join(set([docitem.option
                              for docitem in docitems])).strip()


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
                       % (name, missing_sections.title()))
            extra_sections = self.extra_sections(dir_item)
            if extra_sections is not None:
                err = True
                print ("%s: Extra nonstandard '%s' section found"
                       % (name, extra_sections.title()))
            undoc_options = self.undoc_options(dir_item)
            if undoc_options is not None:
                err = True
                print ("%s: Undocumented configuration option(s): %s"
                       % (name, undoc_options))
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

    @staticmethod
    def missing_sections(subtest_path):
        """
        Return name of any missing required docstring sections

        :param subtest_path: Path to subtest module
        :return: None or name of missing required section
        """
        subtest_doc_sections = SubtestDocSections(subtest_path)
        # Output doesn't matter, only sections instance attr. value
        str(subtest_doc_sections)
        for required in ('summary', 'operational summary'):
            if required not in subtest_doc_sections.sections:
                return required
        return None

    @staticmethod
    def extra_sections(subtest_path):
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

    @staticmethod
    def undoc_options(subtest_path):
        undoc_subtest_config_items = UndocSubtestConfigItems(subtest_path)
        undocumented = str(undoc_subtest_config_items)
        if undocumented:
            return undocumented
        else:
            return None

if __name__ == "__main__":
    STATUS = SubtestsDocumented().check()
    if STATUS:
        sys.exit(-1)
