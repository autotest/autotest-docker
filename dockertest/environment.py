#!/usr/bin/env python

"""
Low-level/standalone host-environment handling/checking utilities/classes/data

:Note: This module must _NOT_ depend on anything in dockertest package or
       in autotest!
"""

import ast
import os.path
import subprocess


class AllGoodBase(object):

    """
    Abstract class representing aggregate True/False value from callables
    """

    #: Mapping of callable name to instance
    callables = None

    #: Mapping of callable name to True/False value
    results = None

    #: Mapping of callable name to detailed results
    details = None

    #: Iterable of callable names to bypass
    skip = None

    def __init__(self, *args, **dargs):
        raise NotImplementedError()

    def __instattrs__(self, skip=None):
        """
        Override class variables with empty instance values

        :param skip: Iterable of callable names to not run
        """

        self.callables = {}
        self.results = {}
        self.details = {}
        if skip is None:
            self.skip = []
        else:
            self.skip = skip

    def __nonzero__(self):
        """
        Implement truth value testing and for the built-in operation bool()
        """

        return False not in self.results.values()

    def __str__(self):
        """
        Make results of individual checkers accessible in human-readable format
        """

        goods = [name for (name, result) in self.results.items() if result]
        bads = [name for (name, result) in self.results.items() if not result]
        if self:  # use self.__nonzero__()
            msg = "All Good: %s" % goods
        else:
            msg = "Good: %s; Not Good: %s; " % (goods, bads)
            msg += "Details:"
            dlst = [' (%s, %s)' % (name, self.detail_str(name))
                    for name in bads]
            msg += ';'.join(dlst)
        return msg

    def detail_str(self, name):
        """
        Convert details value for name into string

        :param name: Name possibly in details.keys()
        :return: String
        """

        return str(self.details.get(name, "No details"))

    #: Some subclasses need this to be a bound method
    def callable_args(self, name):  # pylint: disable=R0201
        """
        Return dictionary of arguments to pass through to each callable

        :param name: Name of callable to return args for
        :return: Dictionary of arguments
        """

        del name  # keep pylint happy
        return dict()

    def call_callables(self):
        """
        Call all instances in callables not in skip, storing results
        """

        _results = {}
        for name, call in self.callables.items():
            if callable(call) and name not in self.skip:
                _results[name] = call(**self.callable_args(name))
        self.results.update(self.prepare_results(_results))

    #: Some subclasses need this to be a bound method
    def prepare_results(self, results):  # pylint: disable=R0201
        """
        Called to process results into instance results and details attributes

        :param results: Dict-like of output from callables, keyed by name
        :returns: Dict-like for assignment to instance results attribute.
        """

        # In case call_callables() overridden but this method is not
        return dict(results)


class EnvCheck(AllGoodBase):

    """
    Represent aggregate result of calling all executables in envcheckdir

    :param config: Dict-like containing configuration options
    :param envcheckdir: Absolute path to directory holding scripts
    """

    #: Dict-like containing configuration options
    config = None

    #: Skip configuration key for reference
    envcheck_skip_option = 'envcheck_skip'

    #: Base path from which check scripts run
    envcheckdir = None

    def __init__(self, config, envcheckdir):
        # base-class __init__ is abstract
        # pylint: disable=W0231
        self.config = config
        self.envcheckdir = envcheckdir
        envcheck_skip = self.config.get(self.envcheck_skip_option)
        # Don't support content less than 'x,'
        if envcheck_skip is None or len(envcheck_skip.strip()) < 2:
            self.__instattrs__()
        else:
            self.__instattrs__(envcheck_skip.strip().split(','))
        for (dirpath, _, filenames) in os.walk(envcheckdir, followlinks=True):
            for filename in filenames:
                fullpath = os.path.join(dirpath, filename)
                relpath = fullpath.replace(self.envcheckdir, '')
                if relpath.startswith('/'):
                    relpath = relpath[1:]
                # Don't add non-executable files
                if not os.access(fullpath, os.R_OK | os.X_OK):
                    continue
                self.callables[relpath] = subprocess.Popen
        self.call_callables()

    def prepare_results(self, results):
        dct = {}
        # Wait for all subprocesses to finish
        for relpath, popen in results.items():
            (stdoutdata, stderrdata) = popen.communicate()
            dct[relpath] = popen.returncode == 0
            self.details[relpath] = {'exit': popen.returncode,
                                     'stdout': stdoutdata,
                                     'stderr': stderrdata}
        return dct

    def callable_args(self, name):
        fullpath = os.path.join(self.envcheckdir, name)
        # Arguments to subprocess.Popen for script "name"
        return {'args': fullpath, 'bufsize': 1, 'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE, 'close_fds': True, 'shell': True,
                'env': self.config}


class SubtestDocs(str):
    """
    A pre-defined rst-format multi-line string documenting a subtest

    :param subtest_path: Full or absolute path, including filename of a
                         subtest module

    """

    header_fmt = ("``%(subtest_name)s`` Subtest\n"
                  "=============================="
                  "=============================="
                  "========\n\n")
    footer_fmt = ("\n")

    def __new__(cls, subtest_path):
        parts = [cls.header(subtest_path),
                 cls.docstring(subtest_path),
                 cls.footer(subtest_path)]
        documentation = '\n'.join(parts)
        return super(SubtestDocs, cls).__new__(cls, documentation)

    @staticmethod
    def filenames(path='.'):
        """
        Return iterable of full path to all subtest modules found under path

        :param path: Relative/Absolute path where 'subtests' directory can
                     be found
        :returns: iterable of full path to all subtest modules found under path
        """
        subtests = []
        subtest_path = os.path.join(os.path.abspath(path), 'subtests')
        for dirpath, _, filenames in os.walk(subtest_path):
            subtest = os.path.basename(dirpath) + '.py'
            if subtest in filenames:
                subtests.append(os.path.join(dirpath, subtest))
        return subtests

    @staticmethod
    def docstring(subtest_path):
        """
        Return cleaned docstring from loading module at subtest_path

        :param subtest_path: Full or absolute path, including filename of a
                             subtest module
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
        Return the standardized name for subtest at subtest_path

        :param subtest_path: Full or absolute path, including filename of a
                             subtest module
        :returns: Standarized docker autotest subtest name
        """
        # Uniformly treat relative or absolute subtest_path
        subtest_path = os.path.abspath(subtest_path)
        # Assume subtest module filename is last
        subtest_path = os.path.dirname(subtest_path)
        subtest_name = subtest_path.partition('subtests')[2]
        return subtest_name.lstrip('/')

    @classmethod
    def header(cls, subtest_path):
        """
        Return a RST formatted section header for subtest

        :param subtest_path: Full or absolute path, including filename of a
                             subtest module
        :returns: RST-format header including docker autotest subtest name
        """
        return cls.header_fmt % {'subtest_name': cls.name(subtest_path)}

    @classmethod
    def footer(cls, subtest_path):
        """
        Return RST-format footer to follow a subtest's documentation

        :param subtest_path: Full or absolute path, including filename of a
                             subtest module
        """
        return cls.footer_fmt % {'subtest_name': cls.name(subtest_path)}

    @classmethod
    def combined(cls, path='.'):
        """
        Search and build documentation from all subtests under path

        :param path: Relative/Absolute path where 'subtests' directory can
                     be found
        :return: String containing RST formated documentation for all subtests
        """
        return cls.join('', [cls(subtest_path)
                             for subtest_path in cls.filenames(path)])

    def html(self):
        """
        Return rendered documentation for subtest as an html fragment

        :param subtest_name: Standarized docker autotest subtest name
        :param path: Relative/Absolute path where 'subtests' directory can
                         be found
        :returns: String, HTML fragment of rendered documentation
        """
        # Requited as this module may not have outside dependencies
        # FIXME: Better place for this code to live?
        try:
            from docutils import core
        except ImportError:
            return ("<p><em><strong>Error:</strong></em>"
                    "docutils not installed</p>")
        # Ref: https://wiki.python.org/moin/ReStructuredText
        # Available formats: html, pseudoxml, rlpdf, docutils_xml, s5_html
        parts = core.publish_parts(source=self, writer_name='html')
        return parts['body_pre_docinfo']+parts['fragment']


def set_selinux_context(pwd, context=None, recursive=True):
    """
    When selinux is enabled it sets the context by chcon -t ...
    :param pwd: target directory
    :param context: desired context (svirt_sandbox_file_t by default)
    :param recursive: set context recursively (-R)
    :raise OSError: In case of failure
    """
    if context is None:
        context = "svirt_sandbox_file_t"
    if recursive:
        flags = 'R'
    else:
        flags = ''
    # changes context in case selinux is supported and is enabled
    _cmd = ("type -P selinuxenabled || exit 0 ; "
            "selinuxenabled || exit 0 ; "
            "chcon -%st %s %s" % (flags, context, pwd))
    cmd = subprocess.Popen(_cmd, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, shell=True)
    if cmd.wait() != 0:
        raise OSError("Fail to set selinux context by '%s' (%s):\nSTDOUT:\n%s"
                      "\nSTDERR:\n%s" % (_cmd, cmd.poll(), cmd.stdout.read(),
                                         cmd.stderr.read()))
