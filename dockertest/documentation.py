"""
Low-level documentation building facilities, depends on external Docutils.

This module shouldn't use any other ``dockertest`` modules it may create
circular-dependencies.  These classes are a bit tricky, due to multiple
input and output formats.  Some familiarity with the `docutils documentation`_
is assumed.

.. _docutils documentation: http://docutils.sourceforge.net/docs/index.html
"""

import ast
import os.path
import docutils
import docutils.core
import docutils.nodes


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
        # Run conversions 3 times to handle any nested keys
        output_string = self.fmt
        for _ in xrange(3):
            try:
                output_string = third(second(first(output_string)))
            except KeyError:
                pass  # Key's missing in content allow to pass through
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
        return input_string % dct

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
            # Disable */** warning, arguments cannot be known ahead of time
            # and using partial's can quickly become unmaintainable.
            # pylint: disable=W0142
            key, value = method(*args)
            subs[key] = value
        return self.do_sub_str(input_string, subs)

    @staticmethod
    def conv(input_string):
        """Perform any final output conversion needed after substitution.
           (nothing by default)"""
        return input_string


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

    #: For summary-only rendering, exclude these section names
    #: (names convert to ids with ``docutils.nodes.make_id()``)
    exclude_names = ('operational detail', 'prerequisites', 'configuration')

    def __init__(self, subtest_path):
        self.subtest_path = subtest_path
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
                return cls(subtest_path)
        raise ValueError("Subtest %s not found under %s/subtests"
                         % (name, os.path.abspath(base_path)))

    def _subs(self, key):
        if key == 'name':
            return self.name(self.subtest_path)
        elif key == 'docstring':
            return self.docstring(self.subtest_path)
        elif key == 'configuration':
            return ''
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

    def html(self, input_string, visitor=None):
        """
        Return input rendered as html snippet, after processing w/ visitor.

        :param input_string: RST-formatted string
        :param visitor: Optional ``Visitor`` class (from
                        ``docutils.nodes.NodeVisitor``)
        """
        # Break it down to aid debugging
        doctree = self.rst2doctree(input_string, visitor)
        _html = self.doctree2html(doctree)
        return _html

    #: Default conversion method to call for final RST rendering
    conv = html

    def html_summary(self, input_string):
        """
        Return input rendered as html snippet, w/ only summary info.

        :param input_string: RST-formatted string
        """

        # Convert section-names into Doctree ids
        _xids = [docutils.nodes.make_id(name) for name in self.exclude_names]

        # Class instantiated in doctree.walkabout() in doctree2html()
        class Visitor(docutils.nodes.SparseNodeVisitor):

            """
            Uses Gang of Four "Visitor" pattern, `impl. ref.`_
.. _impl. ref.: file:///usr/lib/python2.7/site-packages/docutils/nodes.py"""
            # Impossible to fit the link in < 80 chars :S

            @staticmethod
            def visit_section(node):
                """
                Check each section, delete if it matches ``exclude_names``
                """
                # There can be more than one!
                ids = node.get('ids')
                for _id in ids:
                    if _id in _xids:
                        node.parent.remove(node)
                        # Departure calls would fail, skip it entirely
                        raise docutils.nodes.SkipNode()
                    # Otherwise allow this node through

        return self.html(input_string, Visitor)


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

    @property
    def fmt(self):
        """Dynamically represent ``DocBase.fmt`` when referenced

        Any test names referenced in ``exclude`` will be skipped"""
        # Extra keys in ``subs`` excluded here will be ignored
        return '\n\n'.join([('%%(%s)s' % name)
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
