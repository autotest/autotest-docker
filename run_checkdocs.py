#!/usr/bin/env python
"""
Verify all subtests contain required minimum sections, ini's doc all options
"""
import os
import re
import sys
import docutils.nodes
from dockertest.documentation import SubtestDoc
from dockertest.documentation import PretestDoc
from dockertest.documentation import IntratestDoc
from dockertest.documentation import PosttestDoc
from dockertest.documentation import ConfigDoc
from dockertest.documentation import DefaultDoc
from dockertest.documentation import ConfigINIParser


# Generate special SubtestDoc classes from different base classes
# to help check section names and find undocumented config items.
def make_SDS(base_class):
    # Parse rst docstring into doctree, store list of top-level section names
    class SubtestDocSections(base_class):

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
            return ','.join(self.sections)
    return SubtestDocSections

def make_USCI(base_class):
    # Access undocumented test configuration items from high-level interface
    class UndocSubtestConfigItems(base_class):

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
                       % self.name(self.subtest_path))
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
    return UndocSubtestConfigItems


class SubtestsDocumented(object):

    """
    Checker object
    """

    sec_order = ('summary', 'operational summary', 'operational detail',
                 'prerequisites')

    def __init__(self, path='.'):
        """ Location of the subtests.rst directory """
        try:
            self.doc = open(os.path.join(path, 'subtests.rst')).read()
        except IOError:
            print "No subtests.rst file found, perhaps you need to run make"
            sys.exit(-1)
        try:
            self.doc = open(os.path.join(path, 'additional.rst')).read()
        except IOError:
            print "No additional.rst file found, perhaps you need to run make"
            sys.exit(-1)

    def check(self):
        """ Check the subtests tree """
        err = False
        for cls in (SubtestDoc, PretestDoc,
                    IntratestDoc, PosttestDoc):
            failed, dir_tests = self.walk_directories(cls)
            err |= failed
            err |= self.check_missing_tests(dir_tests)
        return err

    def walk_directories(self, cls):
        """ Check directories found by cls """
        dir_tests = cls.module_filenames()
        err = False
        for dir_item in dir_tests:
            # Order of checks (below) is significant
            name = cls.name(dir_item)
            if name.find('example') > -1:
                continue
            SDS_class = make_SDS(cls)
            subtestdocsec = SDS_class(dir_item)
            # Output doesn't matter, only sections instance attr. value
            str(subtestdocsec)

            missing_sections = self.missing_sections(subtestdocsec)
            if missing_sections is not None:
                err = True
                print ("%s: Missing '%s' section"
                       % (name, missing_sections.title()))
            extra_sections = self.extra_sections(subtestdocsec)
            if extra_sections is not None:
                err = True
                print ("%s: Extra nonstandard '%s' section found"
                       % (name, extra_sections.title()))
            if 'configuration' in subtestdocsec.sections:
                err = True
                print ("%s: Hard-coded configuration section found"
                       % name)
            out_of_order = self.section_out_of_order(subtestdocsec)
            if out_of_order is not None:
                err = True
                print ("%s: Out of order section: %s.  Should be: #%d"
                       % (name, out_of_order,
                          # Index is zero-based
                          self.sec_order.index(out_of_order) + 1))
            undoc_options = self.undoc_options(dir_item, cls)
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
    def missing_sections(subtest_doc_sections):
        """
        Return name of any missing required docstring sections

        :param subtest_path: Path to subtest module
        :return: None or name of missing required section
        """
        for required in ('summary', 'operational summary'):
            if required not in subtest_doc_sections.sections:
                return required
        return None

    @staticmethod
    def extra_sections(subtest_doc_sections):
        acceptable = ('prerequisites', 'operational detail',
                      'summary', 'operational summary')
        acceptable = set(SubtestsDocumented.sec_order)
        actual = set(subtest_doc_sections.sections)
        difference = actual - acceptable
        try:
            return difference.pop()
        except KeyError:
            return None

    @staticmethod
    def sec_comes_next(sec, sectidx):
        if sec in sectidx:
            if sectidx[sec] == min(sectidx.values()):
                return True  # Not out of place
            else:
                return False  # Out of place
        else:
            return None

    @staticmethod
    def section_out_of_order(subtest_doc_sections):
        sections = list(subtest_doc_sections.sections)
        sectidx = dict([(val, key) for key, val in enumerate(sections)])

        for act_idx, sec in enumerate(SubtestsDocumented.sec_order):
            # sec_comes_next deletes sec from sectidx
            sec_comes_next = SubtestsDocumented.sec_comes_next(sec, sectidx)
            if (sec_comes_next is not None) and (sec_comes_next is False):
                return sections[act_idx]
            if sec_comes_next is not None:
                del sectidx[sec]  # Remove from min()
        return None

    @staticmethod
    def undoc_options(subtest_path, cls):
        USCI_class = make_USCI(cls)
        undoc_subtest_config_items = USCI_class(subtest_path)
        undocumented = str(undoc_subtest_config_items)
        if undocumented:
            return undocumented
        else:
            return None


if __name__ == "__main__":
    STATUS = SubtestsDocumented().check()
    if STATUS:
        sys.exit(-1)
