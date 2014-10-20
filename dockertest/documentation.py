"""
Low-level documentation building facilities, depends on external Docutils.

This module shouldn't use any other ``dockertest`` modules it may create
circular-dependencies.  These classes are a bit tricky, due to multiple
input and output formats.  Some familiarity with the `docutils documentation`_
is assumed.

.. _docutils documentation: http://docutils.sourceforge.net/docs/index.html
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

from collections import namedtuple
from ConfigParser import RawConfigParser
from StringIO import StringIO
import re
import ast
import os.path
import docutils
import docutils.core
import docutils.nodes
from textwriter import TextWriter

#: Base storage class for each config. doc item
DocItemBase = namedtuple('DocItemBase',
                         ('subthing', 'option', 'desc', 'value'))


class DocItem(DocItemBase):

    """
    Read-only storage class for each config option item's documentation.
    """

    #: String to use when filling in empty value items
    empty_value = '<None>'

    #: Tuple of field-names required by this class
    fields = getattr(DocItemBase, '_fields', None)

    def __new__(cls, *args, **dargs):
        newone = super(DocItem, cls).__new__(cls, *args, **dargs)
        # Special case, make sure empty value's are clear
        if newone.value == '':
            _dct = newone.asdict()
            _dct['value'] = cls.empty_value
            return cls(**_dct)
        else:
            return newone

    def __cmp__(self, other):
        # ConfigParser allows later duplicate options to overwrite prior
        _self = tuple([self.subthing, self.option])
        _other = tuple([other.subthing, other.option])
        # Use tuple comparison / hashing
        return cmp(_self, _other)

    def __hash__(self):
        # Ignore desc and value for comparison purposes, as in __cmp__
        return hash(tuple([self.subthing, self.option]))

    def asdict(self):
        """
        Return copy as an ordered-dictionary
        """
        return self._asdict()


class ConfigINIParser(tuple):

    """
    Parse ``config_defaults`` .ini file into tuple of DocItem instances

    :param ini_filename: Absolute path to a ``.ini`` file
    """

    #: String to use for undocumented options
    undoc_option_doc = 'Undocumented Option, please fix!'

    #: Option-line regular expression.
    # word_chars + opt whitespace + '=' or ':' + opt whitespace + opt value
    cfgoptval_regex = re.compile(r"""(\w+)\s*[=:]{1}\s*(.*)?""", re.IGNORECASE)

    #: Absolute path to the original ``.ini`` file, if one was parsed
    ini_filename = None  # from_string() does not set this

    # Private copy of string in case from_string() was used
    _ini_string = None

    # Private cache for subtest_name property (subtest section name)
    _subtest_name = None

    # Private cache for subsub_names property (sub-subtest section names)
    _subsub_names = None

    # Private cache for subthing_names property (all section names)
    _subthing_names = None

    def __new__(cls, ini_filename):
        # Makes unittesting easier if creation can come from string also
        newone = super(ConfigINIParser,
                       cls).__new__(cls,
                                    cls._new__docitems(open(ini_filename,
                                                            'rb')))
        # Don't depend on __init__ so from_string() can work properly
        newone.ini_filename = ini_filename
        return newone

    # FIXME: set() does not properly identify equivilent DocItem hashes
    @staticmethod
    def _dedupe(docitems):
        docitems_hashes = [docitem.__hash__() for docitem in docitems]
        # Make sure later added item overwrites any prior duplicate
        dedupe_map = {}
        for docitems_index, docitems_hash in enumerate(docitems_hashes):
            # Ordered overwrite of any duplicates
            dedupe_map[docitems_hash] = docitems[docitems_index]
        return tuple(dedupe_map.values())

    @classmethod
    def _new__docitems(cls, iterable):
        docitems = []
        state = {}
        cls.reset_state(state)
        for line in iterable:
            # line continuation begins with whitespace, strip right only.
            result = cls.parse_line(line.rstrip(), state)
            if result is None:
                continue  # state is incomplete
            else:  # state is complete, append then continue
                docitems.append(result)  # overwrite any existing!
        # Last item concluded by EOF?
        if cls.state_complete(state):
            # reset_state() guarantees parameters match for **magic
            lastone = DocItem(**state)
            docitems.append(lastone)  # possibly different one
        return cls._dedupe(docitems)

    @classmethod
    def from_string(cls, ini_string):
        """Return new ConfigINIParser from ``ini_string`` contents"""
        lines = ini_string.splitlines()
        # DO NOT set ini_filename
        newone = super(ConfigINIParser,
                       cls).__new__(cls,
                                    cls._new__docitems(lines.__iter__()))
        # Not accessing a protected member, this method is alternate __new__()
        # pylint: disable=W0212
        # So *_name() properties can work
        newone._ini_string = ini_string
        return newone

    @classmethod
    def reset_state(cls, state, subthing=None):
        """
        In-place modify state to 'incomplete', ready for new data
        """
        # Guarantee state items match DocItem fields exactly
        state.update(DocItem(subthing,
                             None,
                             cls.undoc_option_doc,
                             None).asdict())
        # Presense of these signals a complete state
        del state['option']
        del state['value']
        # The guarantee
        assert not cls.state_complete(state)

    @classmethod
    def parse_line(cls, line, state):
        """
        Parse single line of INI file with state.

        :return: None to continue parsing next line or completed
                 DocItem instance to append.
        """
        # reset_state() guarantees parameters match for **magic
        if line.startswith('[') and line.endswith(']'):
            # Either first section or finishing previous one
            if cls.state_complete(state):
                # Delgate item parsing/storage to DocItem class
                result = DocItem(**state)
            else:
                result = None  # Continue parsing next line
            # Forward parse current line, result encodes any prior state
            cls.reset_state(state, line[1:-1])  # new section
            return result  # state has been updated
        elif line.startswith('#:'):
            result = None  # Continue parsing next line by default
            # Either new option-doc, continuing option/doc, finish previous
            if cls.state_complete(state):  # Already received option/value
                result = DocItem(**state)  # Record, and process line
                # Line must start of a new option's doc
                cls.reset_state(state, state['subthing'])  # same section
            # Either new option-doc, or continuing prior option-doc
            if state['desc'] == cls.undoc_option_doc:  # New option-doc
                state['desc'] = line[2:].strip()
            else:  # continuing prior option-doc
                state['desc'] = '%s %s' % (state['desc'],
                                           line[2:].strip())
            return result  # state has been updated
        else:  # Line must be junk, an option+value, or value-continuation
            return cls.parse_non_section(line, state)

    @staticmethod
    def state_complete(state):
        """Return True if state is complete w/ no None values"""
        state_len = len(state)
        exptd_len = len(DocItem.fields)
        if state_len == exptd_len:
            # No field may be None
            return all([state[field] is not None
                        for field in DocItem.fields])
        else:
            return False

    @classmethod
    def parse_non_section(cls, line, state):
        """Parse a single non-section line from INI file with state"""
        # Determines if this is an option line, junk, or value-continuation
        mobj = cls.cfgoptval_regex.match(line)
        # reset_state() guarantees parameters match for **magic
        if mobj is None:  # Line is value continuation or junk
            # Value-continueation line (3-leading space is minimum)
            if cls.state_complete(state) and line.startswith('   '):
                # Replace multiple leading spaces with single
                line = ' %s' % line.lstrip()
                # Don't leave unnecessary whitespace if first is empty string
                state['value'] = ('%s%s' % (state['value'], line)).strip()
                return None  # Next line could value-continue also
            else:  # line is junk
                if cls.state_complete(state):
                    return DocItem(**state)
                else:
                    return None  # ignore junk
        else:  # line contains at least an unseen option
            # Must be new option+value for desc already recorded or
            # a new undocumented after a prev. undocumented option-doc
            if cls.state_complete(state):  # did not parse this line yet
                result = DocItem(**state)
                cls.reset_state(state, state['subthing'])
            else:  # Not complete yet, maybe line completes it
                result = None  # continue with next line
            # Parse this line, option could have zero or one value
            groups = mobj.groups()
            # Check completion after next line, in case value-continuation
            if len(groups) == 1:  # empty values are possible!
                state['option'], state['value'] = groups[0], ''
            else:  # option w/ value
                state['option'], state['value'] = groups
            return result

    @property
    def subthing_names(self):
        """
        Represent all section names from ``.ini`` file reverse sorted by length

        :raises IOError: On failing to read ``.ini`` file or if no sections
        """
        if self._subthing_names is None:
            # Using different parser here, helps validate job performed
            # in this class is correct (at least for section names)
            parser = RawConfigParser()
            if self.ini_filename is not None:
                parser.read([self.ini_filename])
            else:
                parser.readfp(StringIO(self._ini_string))
            section_names = parser.sections()  # Could be empty!
            if len(section_names) < 1:
                if self.ini_filename is not None:
                    raise IOError("No sections found in ini file: %s"
                                  % self.ini_filename)
                else:
                    raise IOError("No sections found in ini string: '%s'"
                                  % self._ini_string)
            section_names.sort(lambda x, y: cmp(len(x), len(y)), reverse=True)
            self._subthing_names = section_names
        return tuple(self._subthing_names)

    # new_by_name depends on this being static
    @property
    def subtest_name(self):
        """
        Represent standardized subtest name covered by this ``.ini`` file
        """
        # Parsing this is relativly expensive
        if self._subtest_name is None:
            # Handle easy-case first
            if len(self.subthing_names) == 1:
                return self.subthing_names[0]
            else:  # Shortest name must be the subtest
                # Avoid too-deep nesting in length search below
                msg = "Multiple subtest sections found "
                if self.ini_filename is not None:
                    msg = ("%s in ini file: %s" % (msg, self.ini_filename))
                else:
                    msg = ("%s in ini string: '%s'" % (msg, self._ini_string))
                # Must only be one subtest_name
                subtest_name_len = len(self.subthing_names[-1])
                for subthing_name in self.subthing_names[0:-1]:
                    if subtest_name_len == len(subthing_name):
                        raise IOError('%s: subtest "%s" == sub-subtest "%s"'
                                      % (msg, self.subthing_names[-1],
                                         subthing_name))
                self._subtest_name = self.subthing_names[-1]
        return self._subtest_name

    @property
    def subsub_names(self):
        """
        Represent all sub-subtest names (if any) covered by this ``.ini`` file
        """
        if self._subsub_names is None:
            # Simpelest case first
            if len(self.subthing_names) == 1:
                return tuple()
            subsub_names = [subthing_name
                            for subthing_name in self.subthing_names
                            if subthing_name != self.subtest_name]
            self._subsub_names = set(subsub_names)
        return tuple(self._subsub_names)


class SummaryVisitor(docutils.nodes.SparseNodeVisitor):

    """
    Strips all sections in tree-traversal order, matching exclude_names
    """

    #: For summary-only rendering, exclude these section names
    #: (names convert to ids with ``docutils.nodes.make_id()``)
    exclude_names = ('operational detail', 'prerequisites', 'configuration')

    @property
    def xids(self):
        """Represent exclude_names in docutils.node Id format"""
        return [docutils.nodes.make_id(name)
                for name in self.exclude_names]

    def visit_section(self, node):
        """
        Check each section, delete if it matches ``exclude_names``
        """
        # There can be more than one!
        ids = node.get('ids')
        for _id in ids:
            if _id in self.xids:
                node.parent.remove(node)
                # Departure calls would fail, skip it entirely
                raise docutils.nodes.SkipNode()
            # Otherwise allow this node through


class DocBase(object):

    """
    Abstract, *builder* of multi-format output from composite sources.

    ``__init__`` is an optional abstract method, it may be overridden in
    sub-classes for their own particular purposes.
    """

    #: Python string formatting string to compose output from all input
    #: sources.  e.g. ``fmt = "%(beginning)s%(middle)s%(ending)s"``.
    #: Missing keys will pass through literally (probably not desired).
    fmt = ""

    #: Mappings of literal string values for keys in ``fmt``.  Extra
    #: keys/values defined here but not in ``fmt`` will simply be ignored.
    #: e.g. ``{'beginning': 'Avoiding Foobar'}``
    sub_str = None

    #: Mapping of format keys to callables.  Method are
    #: passed ``key`` as their only parameter.  The string returned
    #: from the method will be substituted for ``key`` in  ``fmt``.  e.g.
    #: ``{'ending': self.get_author}`` would call
    #: ``self.get_author("ending")``.
    sub_method = None

    #: Mapping of callable to arguments which return a tuple of strings
    #: in the form ``tuple(fmt_key, fmt_value)``.  None values call w/o
    #: parameters, otherwise value treated as parameter list. e.g.
    #: ``{self.make_middle: ('foo', 'bar', 'baz')}`` call the method
    #: ``self.make_middle`` with ``'foo', 'bar', 'baz'`` as parameters.
    sub_method_args = None

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        """Perform ``fmt % sub_*`` substitutions, then call ``conv_name``"""
        first = self.do_sub_str
        second = self.do_sub_method
        third = self.do_sub_method_args
        output_string = third(second(first(self.fmt)))
        #  Allow optional final conversion modification at runtime
        return self.conv(output_string).strip()

    def do_sub_str(self, input_string, dct=None):
        """Substitute from ``sub_str`` keys/values directly.

        :param input_string: Format string to substitute into
        :param dct: Same as self.sub_str if None, otherwise substitute from."""
        # Allows re-use of this method for other substitutions w/
        # uniform key checking...
        if dct is None:
            if self.sub_str is None:
                return input_string  # nothing to substitute
            dct = self.sub_str
        if dct == {}:
            # Ignore empty dct, let values pass-through w/o substitution
            return input_string
        try:
            return input_string % dct
        except Exception, xcept:
            raise xcept.__class__("%s: fmt='%s' with dct='%s'"
                                  % (xcept.message, input_string, dct))

    def do_sub_method(self, input_string):
        """Substitute from ``sub_method``, key/method-name results"""
        if self.sub_method is None:
            return input_string
        subs = {}
        for key, method in self.sub_method.iteritems():
            subs[key] = str(method(key))
        return self.do_sub_str(input_string, subs)

    def do_sub_method_args(self, input_string):
        """Substitute from calls to ``sub_method_args`` returned
        ``(key, value)``"""
        if self.sub_method_args is None:
            return input_string
        subs = {}
        for method, args in self.sub_method_args.iteritems():
            if args is None:
                args = tuple()
            # reset_state() guarantees parameters match for **magic
            key, value = method(*args)
            subs[key] = value
        return self.do_sub_str(input_string, subs)

    @staticmethod
    def conv(input_string):
        """Perform any final output conversion needed after substitution.
           (nothing by default)"""
        return input_string

    # Helpers for subclass conv. methods

    @staticmethod
    def rst2doctree(rst, visitor=None):
        """
        Returns a (possibly modified) doctree ready for processing/publishing

        :param visitor: optional ``doctutils.nodes.SparseNodeVisitor`` subclass
        :returns: A doctree instance
        """
        # String conversion happened already in ``__new__()``
        doctree = docutils.core.publish_doctree(rst)
        if visitor is not None:
            doctree.walkabout(visitor(doctree))
        return doctree

    @staticmethod
    def doctree2html(doctree):
        """
        Return rendered html fragment from a doctree instance
        """
        # Combined publish_parts() + publish_from_doctree() utilities
        _, publisher = docutils.core.publish_programmatically(
            # TODO: Figure which params not needed & use defaults.
            source=doctree,
            source_path=None,
            source_class=docutils.core.io.DocTreeInput,
            destination_class=docutils.core.io.StringOutput,
            destination=None,
            destination_path=None,
            reader=docutils.core.readers.doctree.Reader(),
            reader_name='null',
            parser=None,
            parser_name='null',
            writer=None,
            writer_name='html',
            settings=None,
            settings_spec=None,
            settings_overrides=None,
            config_section=None,
            enable_exit_status=False)
        parts = publisher.writer.parts
        return parts['body_pre_docinfo'] + parts['fragment']

    @staticmethod
    def doctree2text(doctree):
        """
        Return rendered text string from a doctree instance
        """
        # Combined publish_parts() + publish_from_doctree() utilities
        output, _ = docutils.core.publish_programmatically(
            # TODO: Figure which params not needed & use defaults.
            source=doctree,
            source_path=None,
            source_class=docutils.core.io.DocTreeInput,
            destination_class=docutils.core.io.StringOutput,
            destination=None,
            destination_path=None,
            reader=docutils.core.readers.doctree.Reader(),
            reader_name='null',
            parser=None,
            parser_name='null',
            writer=TextWriter(doctree),
            writer_name='null',
            settings=None,
            settings_spec=None,
            settings_overrides=None,
            config_section=None,
            enable_exit_status=False)
        return output


class SubtestDoc(DocBase):

    """
    Specialized ``DocBase`` to handle a single subtest's documentation.

    :param subtest_path: Full or absolute path, including filename of a
                         subtest module
    """

    fmt = ("``%(name)s`` Subtest\n"
           "=============================="
           "=============================="
           "========\n\n"
           "%(docstring)s\n"
           "%(configuration)s\n")


    #: Cached mapping of test-name to configuration section
    config_cache = None

    def __init__(self, subtest_path, config_cache):
        self.subtest_path = subtest_path
        self.config_cache = config_cache
        # Not many keys, use same method and instance attributes
        self.sub_method = {'name': self._subs,
                           'docstring': self._subs,
                           'configuration': self._subs}

    @classmethod
    def new_by_name(cls, name, base_path='.'):
        """
        Return instance by searching for ``name`` under ``path``

        :param name: Docker autotest standardized name for a subtest
        :param base_path: Relative/Absolute path where ``subtests`` and
                          ``config_defaults`` directories can be found.
        :return: New instance of this class
        :raise ValueError: If subtest ``name`` not found.
        """
        # If this becomes performance bottleneck, implement cls._cache
        for subtest_path in cls.module_filenames(base_path):
            if name.strip() == cls.name(subtest_path):
                _, subtest_configs = ConfigINIParser(base_path).parse()
                return cls(subtest_path, subtest_configs)
        raise ValueError("Subtest %s not found under %s/subtests"
                         % (name, os.path.abspath(base_path)))

    def _subs(self, key):
        name = self.name(self.subtest_path)
        if key == 'name':
            return name
        elif key == 'docstring':
            return self.docstring(self.subtest_path)
        elif key == 'configuration':
            return self.config_cache.get(name, '')
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

    @staticmethod
    def name(subtest_path):
        """
        Return the standardized name for subtest at ``subtest_path``

        :param subtest_path: Relative or absolute filename of subtest module
        :returns: Standardized docker autotest subtest name
        """
        # Uniformly treat relative or absolute subtest_path
        subtest_path = os.path.abspath(subtest_path)
        # Assume subtest module filename is last
        subtest_path = os.path.dirname(subtest_path)
        subtest_name = subtest_path.partition('subtests')[2]
        return subtest_name.lstrip('/')

    @staticmethod
    def module_filenames(base_path='.'):
        """
        Return an iterable of absolute paths to all subtest modules found.

        :param base_path: Relative/Absolute path where ``subtests`` and
                          ``config_defaults`` directories can be found.
        """
        subtests = []
        subtest_path = os.path.join(os.path.abspath(base_path), 'subtests')
        for dirpath, _, filenames in os.walk(subtest_path):
            subtest = os.path.basename(dirpath) + '.py'
            if subtest in filenames:
                subtests.append(os.path.join(dirpath, subtest))
        return tuple(subtests)


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



class RSTDoc(SubtestDoc):

    """
    Render possibly re-formatted RST documentation for a subtest
    """

    @staticmethod
    def raw(input_string):
        """
        Perform no conversion at all, return raw RST format output
        """
        return input_string

    #: Default conversion method to call for final RST rendering
    conv = raw


class SubtestDocs(DocBase):

    """
    Combined output from multiple ``SubtestDoc`` instances

    :param base_path: Relative/Absolute path where searching should begin.
    :param exclude: Customized list of subtests to exclude, None for default
    :param SubtestDocClass: Alternate class to use, None for SubtestDoc
    """

    #: Class to use for instantiating documentation for each subtest
    stdc = SubtestDoc

    #: Absolute path where searching should begin, None if not appropriate
    base_path = '.'

    #: Names of any subtests to exclude from documentation
    exclude = ['example', 'subexample']

    def __init__(self, base_path=None, exclude=None, subtestdocclass=None):
        if base_path is not None:
            self.base_path = os.path.abspath(base_path)
        if exclude is not None:
            self.exclude = exclude
        if subtestdocclass is not None:
            self.stdc = subtestdocclass
        # Cache parsing of all configs.
        config_ini_parser = ConfigINIParser(self.base_path)
        # each subtest can pull it's config section from this dict.
        self._def_rst, self._subtest_configs = config_ini_parser.parse()

    @property
    def fmt(self):
        """Dynamically represent ``DocBase.fmt`` when referenced

        Any test names referenced in ``exclude`` will be skipped"""
        # Extra keys in ``subs`` excluded here will be ignored
        return '%(defaults)s' + '\n\n'.join([('%%(%s)s' % name)
                                             for name in self.names_filenames
                                             if name not in self.exclude])

    @property
    def sub_str(self):
        """Dynamically represent ``DocBase.sub_str`` when referenced

        Any test names referenced in ``exclude`` will be skipped"""
        # list of tuples for initializing dictionary
        lot = []
        for name, filename in self.names_filenames.iteritems():
            if name not in self.exclude:
                lot.append((name, self.stdc(filename, self._subtest_configs)))
        # Add in special defaults section
        defaults = self._def_rst
        lot.append(('defaults', defaults))
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
