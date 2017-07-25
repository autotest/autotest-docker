"""
Parse tabular text output, such as output from 'docker images'
"""

import re
from collections import Mapping, MutableSet, Sequence


class ColumnRanges(Mapping):

    """
    Immutable map of start/end offsets to/from column names.

    :param header: Table header string of multi-space separated column names
    :param expected: Precise number of columns expected, or raise ValueError
    :param min_col_len: Minimum number of characters for a column header
    :raises ValueError: Column < than min_col_len or # columns != expected
    """

    # Too few pub. methods, pylint doesn't count abstract __special_methods__
    # pylint: disable=R0903, W0231

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

    :param table: String of table header, optionally followed by data rows
    :param columnranges: Optional ColumnRanges instance to use
    :param header: Optional header to use, instead of first-line,
                   ignored if columnranges parameter is non-None
    :param tabledata: Optional lines of data to use, optionally with header
                      option or columnranges option (but not both).
    :raises TypeError: if table contains less than one line
    :raises ValueError: if key_column is not in table_columns
    """

    #: Permit duplicate rows to be added
    allow_duplicate = False

    #: Comparison function to use when sorting
    compare = None

    # internal cache of column name to tuple of start,end offset range
    columnranges = None

    #: internal cache of parsed rows
    _rows = None

    def __init__(self, table, columnranges=None, header=None, tabledata=None):
        # pylint: disable=W0231
        if columnranges is not None and header is not None:
            raise ValueError("Cannot specify both columnranges and header "
                             "parameters")

        if header is None and tabledata is None:
            table_lines = table.strip().splitlines()
            if len(table_lines) < 1:
                # FIXME: This should probably be a ValueError
                raise TypeError("Table shorter than one line: %s" % table)
            header, tabledata = self.parseheader(table)
        elif header is None:
            # tabledata == tabledata
            table_lines = tabledata.strip().splitlines()
            header = table_lines[0]
        else:  # tabledata == none
            tabledata = table_lines.strip().splitlines()

        if columnranges is None:
            # First line is header
            self.columnranges = ColumnRanges(header)
        else:
            if not isinstance(columnranges, ColumnRanges):
                raise TypeError("columnranges is not a ColumnRanges instance")
            self.columnranges = columnranges

        self._rows = []

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

    def discard(self, value):
        """
        Wraps del texttable[index[
        """
        return self.__delitem__(value)

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

    @staticmethod
    def parseheader(table):
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

    @staticmethod
    def parserows(tabledata):
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

    def search(self, col_name, value, match_func=None):
        """
        Returns a list of dictionaries containing col_name key with value

        :param col_name: Column name string to use
        :param value: Value to compare each row's column name to
        :match_func: If specified, match found when
                     match_func(col_name, value, row_value) returns True
        """
        result = []
        for row in self._rows:
            if match_func is None:
                if row.get(col_name) == value:
                    result.append(dict(row))
            else:
                if match_func(col_name, value, row.get(col_name)):
                    result.append(dict(row))
        return result

    def find(self, col_name, value, match_func=None):
        """
        Return dictionary with key col_name == value raise IndexError if != 1
        """
        found = self.search(col_name, value, match_func)
        if len(found) != 1:
            raise IndexError("Found %d rows with %s == %s"
                             % (len(found), col_name, value))
        return found[0]
