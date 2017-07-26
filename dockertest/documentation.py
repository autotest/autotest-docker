"""
Documentation building facilities, depends on external Docutils and
documentation_deps

This module shouldn't use any other ``dockertest`` modules it may create
circular-dependencies.  Some familiarity with the `docutils documentation`_
is assumed.

.. _docutils documentation: http://docutils.sourceforge.net/docs/index.html
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import ast
import os.path
from docdeps import ConfigINIParser
from docdeps import SummaryVisitor
from docdeps import DocBase


class DefaultDoc(DocBase):

    """
    Specialized ``DocBase`` singleton that only handles Default configuration

    :param ini_path: Optional, full or absolute path to defaults file.
    """

    #: Path to ini file, None if not parsed
    ini_path = None

    #: Contains a tuple of DocItems parsed or None if not
    docitems = None

    #: String format for each option, desc, value item in a DocItem
    item_fmt = '*  ``%(option)s`` : (``%(value)s``) %(desc)s'

    #: Default base-path to use for all methods requiring one.
    default_base_path = '.'  # important for unittesting!

    #: Class-reference to DefaultDoc instance singleton, if not None.
    singleton = None

    # Private cache for quickly looking up a default option by name
    _default_map = None

    def __new__(cls, ini_path=None):
        """Create new universal (singleton) instance, if none exist."""
        if cls.singleton is None:
            if ini_path is None and cls.ini_path is None:
                ini_path = os.path.join(cls.default_base_path,
                                        'config_defaults',
                                        'defaults.ini')
                ini_path = os.path.abspath(ini_path)
            elif ini_path is None:
                ini_path = os.path.abspath(cls.ini_path)
            else:  # ini_path is not None but cls.ini_path is None
                cls.ini_path = os.path.abspath(ini_path)
            cls.singleton = super(DefaultDoc, cls).__new__(cls)
            cls.singleton.ini_path = os.path.abspath(ini_path)  # Just in case
            cls.singleton.docitems = ConfigINIParser(cls.singleton.ini_path)
        # In all cases, return only the singleton instance
        return cls.singleton

    @property
    def fmt(self):
        """
        Represent entire contents of defaults configuration section.
        """
        if not self.docitems:
            raise ValueError("No defaults.ini options were parsed from %s"
                             % self.ini_path)
        _fmt = ''
        lines = [self.item_fmt % docitem.asdict()
                 for docitem in self.docitems]
        # Append to existing _fmt
        _fmt = '%s%s\n\n' % (_fmt, '\n'.join(lines))
        return _fmt

    def get_default(self, option):
        """Returns docitem for Default option, None if it doesn't exist"""
        if self._default_map is None:
            options = [docitem.option for docitem in self.docitems]
            self._default_map = dict(zip(options, self.docitems))
        return self._default_map.get(option, None)


class ConfigDoc(DocBase):

    """
    Specialized ``DocBase`` to handle single configuration section + subsection

    :param ini_path: Full or absolute path, including filename of config. file
    """

    #: Path to ini file, None if not parsed
    ini_path = None

    #: Contains a tuple of DocItems parsed or None if not
    docitems = None

    #: String format for each non-default option, desc, value item in a DocItem
    item_fmt = DefaultDoc.item_fmt

    #: String format for any overridden default option, w/ cross-reference
    def_item_fmt = ('*  ``%(option)s`` : ``%(value)s`` '
                    ':ref:`Overrides default value '  # required for cross-file
                    '<default configuration options>`: ``%(def_value)s``')

    #: String format for any subtest options inherited by sub-subtest
    inherit_fmt = DefaultDoc.item_fmt + ' - *inherited*'

    #: Default base-path to use for all methods requiring one.
    default_base_path = '.'  # important for unittesting!

    def __init__(self, ini_path):
        self.ini_path = ini_path
        self.docitems = ConfigINIParser(self.ini_path)

    @classmethod
    def new_by_name(cls, name, base_path=None):
        """
        Return instance by searching for ``name`` under ``path``

        :param name: Subtest name or 'DEFAULTS' (NOT sub-subtest names!)
        :param base_path: Relative/Absolute path where ``config_defaults``
                          directory can be found. Uses
                          ``cls.default_base_path`` if None.
        :return: New instance of this class
        :raise ValueError: If subtest ``name`` not found.
        """
        if base_path is None:
            base_path = cls.default_base_path
        # If this becomes performance bottleneck, implement cls._cache
        for ini_path in cls.ini_filenames(base_path):
            inst = cls(ini_path)
            if name.strip() == inst.docitems.subtest_name:
                return inst
        raise ValueError("Subtest %s not found under %s/config_defaults"
                         % (name, os.path.abspath(base_path)))

    @property
    def fmt(self):
        """
        Represent entire contents of configuration section (if any)
        """
        # Handle simple case first
        if not self.docitems:
            return ''
        _fmt = '\n\nConfiguration\n---------------\n\n'
        ssns = ["``%s``" % ssn for ssn in self.docitems.subsub_names]
        if ssns:
            subsublist = ':Sub-subtests: %s' % ', '.join(ssns)
            _fmt = '%s%s\n\n' % (_fmt, subsublist)
        general_fmt = self._general_fmt()  # Could be empty
        if len(general_fmt) > 1:  # In case stray newline
            _fmt = '%s\n%s\n' % (_fmt, general_fmt)
        # Only include subsub section if it has items to document
        subsub_fmt = self._subsub_fmt()  # Also could be empty
        if len(subsub_fmt) > 1:
            # Section headers will be embedded
            _fmt = '%s\n%s\n' % (_fmt, subsub_fmt)
        return _fmt

    def _fmt_options(self, options, inherited=None):
        """
        Private ``fmt()`` helper for ``_general_fmt()`` and ``_subsub_fmt()``
        """
        if inherited is None:
            inherited = []  # Makes conditional smaller (below)
        undoc_doc = ConfigINIParser.undoc_option_doc
        defaults = DefaultDoc()  # singleton!
        lines = []
        for option in options:
            op_dct = option.asdict()
            default = defaults.get_default(option.option)
            if default is not None:  # Overridden default option
                op_dct['def_value'] = default.value
                line_fmt = self.def_item_fmt
            else:
                if option.desc == undoc_doc and option.option in inherited:
                    line_fmt = self.inherit_fmt
                    # inherited maps subtest option name, to its docitem
                    op_dct['desc'] = inherited[option.option].desc
                else:  # Standard formatting
                    line_fmt = self.item_fmt
            lines.append(line_fmt % op_dct)
        return lines

    def _general_fmt(self):
        """
        Private helper for fmt() to render all subtest options, if any.
        """
        # Could be completely empty
        general_options = [docitem
                           for docitem in self.docitems
                           if docitem.subthing == self.docitems.subtest_name]
        # Remove subsubtests option if present
        general_options = [docitem for docitem in general_options
                           if docitem.option != 'subsubtests']
        return '\n'.join(self._fmt_options(general_options))

    def _subsub_fmt(self):
        """
        Private helper for fmt() to render all sub-subtest sections + options
        """
        # Sub-subtests inherit options from parent subtest
        inherited = dict([(di.option, di) for di in self.docitems
                          if di.subthing == self.docitems.subtest_name])
        # Organize sub-subtest content by name for unroll into sections
        subsubs = dict([(subsub_name, [])
                        for subsub_name in self.docitems.subsub_names])
        for docitem in [di for di in self.docitems
                        if di.subthing in subsubs]:
            subsubs[docitem.subthing].append(docitem)
        # Unroll each section's items under one heading per section
        lines = []
        for subsub_name in subsubs:
            if not subsubs[subsub_name]:
                continue  # Skip sections w/o any content
            lines.append('')  # blank before section content
            lines.append('``%s`` Sub-subtest' % subsub_name)  # Section heading
            lines.append('~' * (len(lines[-1]) + 2))
            lines.append('')  # blank before section title
            lines += self._fmt_options(subsubs[subsub_name], inherited)
        return '\n'.join(lines)

    # Makefile depends on this being static
    @classmethod
    def ini_filenames(cls, base_path=None):
        """
        Return an iterable of absolute paths to all ini files found.

        :param base_path: Relative/Absolute path where ``subtests`` and
                          ``config_defaults`` directories can be found.
                          Uses ``cls.default_base_path`` if None.
        """
        if base_path is None:
            base_path = cls.default_base_path
        ini_files = []
        ini_path = os.path.join(os.path.abspath(base_path),
                                'config_defaults')
        for dirpath, _, filenames in os.walk(ini_path):
            for filename in filenames:
                if filename == 'defaults.ini':
                    continue  # processed separately
                if filename.endswith('.ini'):
                    ini_files.append(os.path.join(dirpath, filename))
        return tuple(ini_files)


class SubtestDoc(DocBase):

    """
    Specialized ``DocBase`` to handle a single subtest's documentation.

    :param subtest_path: Full or absolute path, including filename of a
                         subtest module
    """

    fmt = ("``%(name)s`` %(postfix)s\n"
           "=============================="
           "=============================="
           "========\n\n"
           "%(docstring)s\n\n"
           "%(configuration)s\n")

    #: String to use for tests w/o any configuration
    NoINIString = '\n:Note: Subtest does not have any default configuration\n'

    #: Class to use for parsing documentation
    ConfigDocClass = ConfigDoc  # important for unittesting!

    #: Default base-path to use for all methods requiring one.
    default_base_path = '.'  # important for unittesting!

    #: Top level directory name base and name postfix for instances.
    tld_name = 'subtests'
    name_postfix = 'Subtest'

    def __init__(self, subtest_path):
        self.subtest_path = subtest_path
        self.sub_str = {'postfix': self.name_postfix}
        # Not many keys, use same method and instance attributes
        self.sub_method = {'name': self._subs,
                           'docstring': self._subs,
                           'configuration': self._subs}

    @classmethod
    def new_by_name(cls, name, base_path=None):
        """
        Return instance by searching for ``name`` under ``path``

        :param name: Docker autotest standardized name for a subtest
        :param base_path: Relative/Absolute path where ``subtests`` and
                          ``config_defaults`` directories can be found.
                          ``cls.default_base_path`` used if ``None``.
        :return: New instance of this class
        :raise ValueError: If subtest ``name`` not found.
        """
        if base_path is None:
            base_path = cls.default_base_path
        for subtest_path in cls.module_filenames(base_path):
            if name.strip() == cls.name(subtest_path):
                return cls(subtest_path)
        raise ValueError("Subtest %s not found under %s/subtests"
                         % (name, os.path.abspath(base_path)))

    def _subs(self, key):
        """Private helper for ``str()`` handling of ``sub_method`` for ``key``
        """
        name = self.name(self.subtest_path)
        if key == 'name':
            return name
        elif key == 'docstring':
            return self.docstring(self.subtest_path)
        elif key == 'configuration':
            try:
                new_by_name = self.ConfigDocClass.new_by_name
                configdoc = new_by_name(self.name(self.subtest_path))
            except (ValueError, AttributeError):  # ConfigDocClass can be None
                return self.NoINIString
            return configdoc
        else:
            raise KeyError('Unknown fmt key "%s" passed to _subs()' % key)

    @staticmethod
    def docstring(subtest_path):
        """
        Return cleaned docstring from loading module at ``subtest_path``

        :param subtest_path: Relative/absolute path to a subtest module
        :returns: Python-parsed docstring from module file
        """
        # Uniformly treat relative or absolute subtest_path
        subtest_path = os.path.abspath(subtest_path)
        # Using ast on a string avoids all module-import problems
        source = open(subtest_path, 'rb').read()
        # 'exec' means "multiple lines of source code"
        node = ast.parse(source, subtest_path, 'exec')
        return ast.get_docstring(node)

    # new_by_name depends on this being static
    @classmethod
    def name(cls, subtest_path):
        """
        Return the standardized name for subtest at ``subtest_path``

        :param subtest_path: Relative or absolute filename of subtest module
        :returns: Standardized docker autotest subtest name
        """
        # Uniformly treat relative or absolute subtest_path
        subtest_path = os.path.abspath(subtest_path)
        # Assume subtest module filename is last
        subtest_path = os.path.dirname(subtest_path)
        subtest_name = subtest_path.partition(cls.tld_name)[2]
        return subtest_name.lstrip('/')

    # Makefile depends on this being a static
    @classmethod
    def module_filenames(cls, base_path=None):
        """
        Return an iterable of absolute paths to all subtest modules found.

        :param base_path: Relative/Absolute path where ``subtests`` and
                          ``config_defaults`` directories can be found.
                          Uses ``cls.default_base_path`` if None.
        """
        if base_path is None:
            base_path = cls.default_base_path
        subtests = []
        subtest_path = os.path.join(os.path.abspath(base_path), cls.tld_name)
        for dirpath, _, filenames in os.walk(subtest_path):
            subtest = os.path.basename(dirpath) + '.py'
            if subtest in filenames:
                subtests.append(os.path.join(dirpath, subtest))
        return tuple(subtests)

    # Optional, alternate conv methods

    def html(self, input_string):
        """
        (conv method) Render as html snippet.

        :param input_string: RST-formatted string
        :param visitor: Optional ``Visitor`` class (from
                        ``docutils.nodes.NodeVisitor``)
        """
        return self.doctree2html(self.rst2doctree(input_string))

    def html_summary(self, input_string):
        """
        (conv method) Render as html snippet, w/ only summary info.

        :param input_string: RST-formatted string
        """
        return self.doctree2html(self.rst2doctree(input_string,
                                                  SummaryVisitor))

    def rst_summary(self, input_string):
        """
        (conv method) Render as RST w/ only summary info.

        :param input_string: RST-formatted string
        """
        return self.doctree2text(self.rst2doctree(input_string,
                                                  SummaryVisitor))


# TODO: Fix this pylint with class factory in base-class?
# Additional public methods not needed, only attributes needed to
# differientiate.
class PretestDoc(SubtestDoc):  # pylint: disable=R0903

    """Subclass to represent pretest module documentation"""
    #: Top level directory name base and name postfix for instances.
    tld_name = 'pretests'
    name_postfix = 'Pre-test'


class IntratestDoc(SubtestDoc):  # pylint: disable=R0903

    """Subclass to represent intratest module documentation"""
    #: Top level directory name base and name postfix for instances.
    tld_name = 'intratests'
    name_postfix = 'Intra-test'


class PosttestDoc(SubtestDoc):  # pylint: disable=R0903

    """Subclass to represent posttest module documentation"""
    #: Top level directory name base and name postfix for instances.
    tld_name = 'posttests'
    name_postfix = 'Post-test'


class SubtestDocs(DocBase):

    """
    Combined output from multiple ``SubtestDoc`` instances

    :param base_path: Relative/Absolute path where searching should begin.
                      Uses ``self.default_base_path`` if None.
    :param exclude: Customized list of subtests to exclude, None for default
    :param SubtestDocClass: Alternate class to use, None for SubtestDoc
    :param contents: True to prefix with RST ``...contents::`` block.
    """

    #: Class to use for instantiating documentation for each subtest
    stdc = SubtestDoc

    #: Absolute path where searching should begin, None if not appropriate
    base_path = None

    #: Default base path to use if base_path is None
    default_base_path = '.'

    #: Names of any subtests to exclude from documentation
    exclude = ['example', 'subexample', 'pretest_example',
               'intratest_example', 'posttest_example']

    #: Default contents block to include before all other sections
    contents = ".. contents::\n   :depth: 1\n   :local:\n\n"

    def __init__(self, base_path=None, exclude=None, subtestdocclass=None,
                 contents=True):
        if not contents:
            self.contents = ''
        if base_path is None:
            self.base_path = os.path.abspath(self.default_base_path)
        else:
            self.base_path = os.path.abspath(base_path)
        if exclude is not None:
            self.exclude = exclude
        if subtestdocclass is not None:
            self.stdc = subtestdocclass

    @property
    def fmt(self):
        """Dynamically represent ``DocBase.fmt`` when referenced

        Any test names referenced in ``exclude`` will be skipped"""
        # Extra keys in ``subs`` excluded here will be ignored
        subtest_fmt = [('%%(%s)s' % name)
                       for name in self.names_filenames
                       if name not in self.exclude]
        subtest_fmt.sort()
        return "%s%s\n" % (self.contents, '\n\n'.join(subtest_fmt))

    @property
    def sub_str(self):
        """Dynamically represent ``DocBase.sub_str`` when referenced

        Any test names referenced in ``exclude`` will be skipped"""
        # list of tuples for initializing dictionary
        lot = []
        for name, filename in self.names_filenames.iteritems():
            if name not in self.exclude:
                lot.append((name, self.stdc(filename)))
        # Excluded names not present in ``fmt`` will be ignored
        return dict(lot)

    @property
    def names_filenames(self):
        """Represent mapping of subtest name to absolute filename

        *Includes* test names referenced in ``exclude``"""
        # list of tuples for initializing dictionary
        lot = [(self.stdc.name(path), path)
               for path in self.stdc.module_filenames(self.base_path)]
        # let higher-level methods sort out the contents as needed
        return dict(lot)


def set_default_base_path(base_path):
    """Modify all relevant classes ``default_base_path`` to base_path"""
    # Order is significant!
    for cls in (SubtestDocs, ConfigDoc, SubtestDoc.ConfigDocClass, DefaultDoc):
        cls.default_base_path = base_path
