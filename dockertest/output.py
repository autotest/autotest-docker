"""
Handlers for command-line output processing, crash/panic detection, etc.
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import warnings
import re
from collections import Mapping, MutableSet, Sequence

import xceptions
from environment import AllGoodBase


class DockerVersion(object):

    """
    Parser of docker-cli version command output as client/server properties
    """
    #: Raw, possibly empty or multi-line output from docker version command.
    #: Read-only, set in __init__
    version_string = None
    #: Line-split version of version_string, not stripped, read-only, set in
    #: __init__
    version_lines = None
    _client = None
    _server = None

    def __init__(self, version_string):
        """
        Initialize version command output parser instance

        :param version_string: Raw, possibly empty or multi-line output
                               from docker version command.
        """
        self.version_string = version_string
        self.version_lines = self.version_string.splitlines()

    @property
    def client(self):
        """
        Read-only property representing version-number string of docker client
        """
        if self._client is None:
            regex = re.compile(r'Client\s+version:\s+(\d+\.\d+\.\d+)',
                               re.IGNORECASE)
            mobj = None
            for line in self.version_lines:
                mobj = regex.search(line.strip())
                if bool(mobj):
                    self._client = mobj.group(1)
        if self._client is None:
            raise xceptions.DockerOutputError("Couldn't parse client version "
                                              "from %s" % self.version_string)
        return self._client

    @property
    def server(self):
        """
        Read-only property representing version-number string of docker server
        """
        if self._server is None:
            regex = re.compile(r'Server\s*version:\s*(\d+\.\d+\.\d+)',
                               re.IGNORECASE)
            mobj = None
            for line in self.version_lines:
                mobj = regex.search(line.strip())
                if bool(mobj):
                    self._server = mobj.group(1)
        if self._server is None:
            raise xceptions.DockerOutputError("Couldn't parse server version "
                                              "from %s" % self.version_string)
        return self._server


class ColumnRanges(Mapping):

    """
    Immutable map of start/end offsets to/from column names.
    """

    __slots__ = ('ranges', 'columns', 'count')

    #: Iterable of start/end character-offset tuples corresponding to columns
    ranges = None

    #: Iterable of column names corresponding to ranges
    columns = None

    #: Number of columns/ranges
    count = None

    #: Regex specifying the column separator
    _re = re.compile(r"\s\s+")

    def __init__(self, header, min_col_len=3, expected=None):
        """
        Initialize immutable mapping from header string.

        :param header: Table header string of multi-space separated column names
        :param expected: Precise number of columns expected, or raise ValueError
        :param min_col_len: Minimum number of characters for a column header
        :raises ValueError: Column < than min_col_len or # columns != expected
        """
        header_strip = header.strip()  # just in case
        cols = [col for col in self._re.split(header_strip)]
        if expected is not None and len(cols) != expected:
            raise ValueError("Columns parsed (%s) does not match expected (%s)"
                             % (cols, expected))
        columns = []  # converted to set at end then discarded
        starts = []  # zip()'d at end then discarded
        for col in cols:
            col_strip = col.strip()
            if len(col_strip) < min_col_len:
                raise ValueError("Column name '%s' is smaller than minimum "
                                 "required column name length %d"
                                 % (col_strip, min_col_len))
            columns.append(col_strip)
            starts.append(header_strip.index(col_strip))  # lookup char offset
        ends = starts[1:] + [None]  # ending offsets EXCLUSIVE for range()
        # Stored separetly b/c dict() storage would be un-ordered!
        self.columns = tuple(columns)
        ranges = zip(starts, ends)  # needed for exception message
        self.ranges = tuple(ranges)
        self.count = len(columns)  # allow check for duplicates vs set()
        # Check duplicate column names or ranges
        if (self.count != len(set(self.ranges)) or
                self.count != len(set(self.columns))):
            raise ValueError("Duplicate column names '%s' or ranges '%s' "
                             "detected: " % (columns, ranges))

    def __str__(self):
        lst = [("%s: %s-%s" % (col, start, end))
               for col, (start, end) in zip(self.columns, self.ranges)
               if end > 0]
        lst.append("%s: %s-End" % (self.columns[-1], self.ranges[-1][0]))
        return ", ".join(lst)

    def __repr__(self):
        return "<%s object of {%s}>" % (self.__class__.__name__,
                                        str(self))

    def __len__(self):
        return self.count  # instance is immutable

    def __contains__(self, item):
        return item in self.ranges or item in self.columns

    def __iter__(self):
        return self.ranges.__iter__()

    def __getitem__(self, key):
        try:
            return self.columns[list(self.ranges).index(key)]
        except ValueError:
            return self.ranges[list(self.columns).index(key)]

    def offset(self, offset):
        """
        Return column name corresponding to range containing offset

        :param offset: Character offset number to lookup
        :returns: Column name string
        :raises IndexError: if offset not found in any header range
        """
        if offset is None or offset < 0:
            return self.columns[-1]
        for index, (start, end) in enumerate(self.ranges):
            if end is None:
                return self.columns[-1]
            if offset in xrange(start, end):
                return self.columns[index]
        if offset > 0:
            return self.columns[-1]  # beyond end of any ranges


class TextTable(MutableSet, Sequence):

    """
    Parser for tabular data with values separated by character offsets
    """

    #: Permit duplicate rows to be added
    allow_duplicate = False

    #: Comparison function to use when sorting
    compare = None

    # internal cache of column name to tuple of start,end offset range
    columnranges = None

    #: internal cache of parsed rows
    _rows = None

    def __init__(self, table):
        """
        Initialize to hold data mapped from table header, & optionally data

        :param table: String of table header, optionally followed by data rows
        :raises TypeError: if table contains less than one line
        :raises ValueError: if key_column is not in table_columns
        """
        self._rows = []
        header, tabledata = self.parseheader(table)
        self.columnranges = ColumnRanges(header)
        if tabledata is not None:
            for line in self.parserows(tabledata):
                line_strip = line.strip()
                self.append(self.parse_line(line_strip))

    def __eq__(self, other):
        if not hasattr(other, '__iter__'):
            return False
        return list(self._rows) == list(other)

    def __len__(self):
        return len(self._rows)

    def __iter__(self):
        return self._rows.__iter__()

    def __contains__(self, value):
        """
        Return true if any row or row[self.key_column] equals value
        """
        return self._rows.__contains__(value)

    def __setitem__(self, index, value):
        self.conform_or_raise(value)
        return self._rows.__setitem__(index, value)

    def __delitem__(self, index):
        return self._rows.__delitem__(index)

    def __getitem__(self, index):
        return self._rows.__getitem__(index)

    def insert(self, index, value):
        """
        Insert value contents at index
        """
        self.conform_or_raise(value)
        return self._rows.insert(index, value)

    def add(self, value):
        self.conform_or_raise(value)
        return self._rows.append(value)

    def discard(self, index):
        """
        Wrapps del texttable[index[
        """
        return self.__delitem__(index)

    def append(self, value):
        """
        Inserts value item or iterable at end
        """
        self.conform_or_raise(value)
        return self._rows.append(value)

    def conforms(self, value):
        """
        Return True if value is non-duplicate dict-like with all column keys
        """
        try:
            self.conform_or_raise(value)
            return True
        except ValueError:
            return False

    def conform_or_raise(self, value):
        """Raise ValueError if not self.conforms(value)"""
        if not isinstance(value, dict):
            raise ValueError("Value '%s' is not a dict-like" % value)
        keys = set(value.keys())
        expected = set(self.columnranges.values())
        if keys == expected:
            if not self.allow_duplicate and self.__contains__(value):
                raise ValueError("Value '%s' is duplicate" % value)
        else:
            raise ValueError("Value's keys %s != %s columns"
                             % (keys, expected))

    @staticmethod
    def value_filter(value):
        """
        Converts empty stripped or '<none>' strings into None value
        """
        value = str(value).strip()
        if value == '':
            return None
        if value == '<none>':
            return None
        return value

    def parseheader(self, table):
        """
        Parse string into tuple(header, data)
        """
        lines = table.strip().splitlines()
        if len(lines) < 1:
            raise TypeError("Table shorter than one line: %s" % table)
        if len(lines) == 1:
            tabledata = None
        else:
            tabledata = "\n".join(lines[1:])  # put back together
        return (lines[0], tabledata)  # both regular strings

    def parserows(self, tabledata):
        """
        Parse table data string (minus header line) into a list of rows
        """
        return tabledata.strip().splitlines()

    def parse_line(self, line):
        """
        Parse one line into a dict based on columnranges
        """
        newdict = {}
        strippedline = line.strip()
        for (start, end), colname in self.columnranges.items():
            newdict[colname] = self.value_filter(strippedline[start:end])
        return newdict

    def search(self, col_name, value):
        """
        Returns a list of dictionaries containing col_name key with value
        """
        result = []
        for row in self._rows:
            if row.get(col_name) == value:
                result.append(dict(row))
        return result

    def find(self, col_name, value):
        """
        Return dictionary with key col_name == value raise IndexError if != 1
        """
        found = self.search(col_name, value)
        if len(found) != 1:
            raise IndexError("Found %d rows with %s == %s"
                             % (len(found), col_name, value))
        return found[0]

class OutputGoodBase(AllGoodBase):

    """
    Compare True if all methods ending in '_check' return True on stdout/stderr
    """

    #: Reference to original CmdResult instance
    cmdresult = None

    #: Stripped standard-output string
    stdout_strip = None

    #: Stripped standard-error string
    stderr_strip = None

    def __init__(self, cmdresult, ignore_error=False, skip=None):
        """
        Run checks, define result attrs or raise xceptions.DockerOutputError

        :param cmdresult: autotest.client.utils.CmdResult instance
        :param ignore_error: Raise exceptions.DockerOutputError if False
        :param skip: Iterable of checks to bypass, None to run all
        """
        self.cmdresult = cmdresult
        self.stdout_strip = cmdresult.stdout.strip()
        self.stderr_strip = cmdresult.stderr.strip()
        # All methods called twice with mangled names, mangle skips also
        if skip is not None:
            newskip = []
            for checker in skip:
                newskip.append(checker + '_stdout')
                newskip.append(checker + '_stderr')
        else:
            newskip = skip
        self.__instattrs__(newskip)
        for checker in [name for name in dir(self) if name.endswith('_check')]:
            self.callables[checker + '_stdout'] = getattr(self, checker)
            self.callables[checker + '_stderr'] = getattr(self, checker)
        self.call_callables()
        # Not nonzero means One or more checkers returned False
        if not ignore_error and not self.__nonzero__():
            # Str representation will provide details
            raise xceptions.DockerOutputError(str(self))

    def callable_args(self, name):
        if name.endswith('_stdout'):
            return {'output': self.stdout_strip}
        elif name.endswith('_stderr'):
            return {'output': self.stderr_strip}
        else:
            raise RuntimeError("Unexpected check method name %s" % name)

    def prepare_results(self, results):
        duplicate = False
        for checker, passed in results.items():
            if not passed and not duplicate:
                exit_status = self.cmdresult.exit_status
                stdout = self.cmdresult.stdout.strip()
                stderr = self.cmdresult.stderr.strip()
                detail = 'Command '
                if exit_status != 0:
                    detail += 'exit %d ' % exit_status
                if len(stdout) > 0:
                    detail += 'stdout "%s" ' % stdout
                if len(stderr) > 0:
                    detail += 'stderr "%s".' % stderr
                self.details[checker] = detail
                duplicate = True  # all other failures will be same
        return super(OutputGoodBase, self).prepare_results(results)

    # FIXME: Deprecate self.output_good in Major/Minor release
    @property
    def output_good(self):
        """
        Deprecated, do not use!
        """
        warnings.warn(PendingDeprecationWarning())
        # Make sure PrepareResults gets called
        self.__nonzero__()
        og = {}
        for key, value in self.results.items():
            basekey = key.replace('_stdout', '')
            basekey = basekey.replace('_stderr', '')
            # Represent result as logical and of both stdout/stderr values
            if basekey in og:
                og[basekey] = og[basekey] and value
            else:
                og[basekey] = value
        return og


class OutputGood(OutputGoodBase):

    """
    Container of standard checks
    """

    @staticmethod
    def crash_check(output):
        """
        Return False if Go panic string found in output

        :param output: Stripped output string
        :return: True if Go panic pattern **not** found
        """
        regex = re.compile(r'\s*panic:\s*.+error.*')
        for line in output.splitlines():
            if bool(regex.search(line.strip())):
                return False  # panic message found
        return True  # panic message not found

    @staticmethod
    def usage_check(output):
        """
        Return False if 'Docker usage' pattern found in output

        :param output: Stripped output string
        :return: True if usage message pattern **not** found
        """
        regex = re.compile(r'\s*usage:\s+docker\s+.*', re.IGNORECASE)
        for line in output.splitlines():
            if bool(regex.search(line.strip())):
                return False  # usage message found
        return True  # usage message not found

    @staticmethod
    def error_check(output):
        """
        Return False if 'Error: ' pattern found in output

        :param output: Stripped output string
        :return: True if 'Error: ' does **not** sppear
        """
        for line in output.splitlines():
            if line.lower().strip().count('error: '):
                return False
        return True

    # TODO: Other checks?
