"""Classes to assist with serial inspection of asynchronous output"""

import os
import select
import re
from time import time


class UnseenLines(object):
    """
    Non-blocking reader that returns yet unseen-lines.  Requires
    frequent calls to ``flush()`` and/or ``nextline()`` to prevent
    the producer from blocking.

    :param infd: Open file descriptor to read
    """

    #: Max time to wait for new input on each read call
    POLL_MILISECONDS = 10

    #: Pattern that will be stripped from input
    STRIP_REGEX = re.compile(r'(\x1b[][]([0-9\;\?h]+)?(.+\x07)?)|(\r)')

    #: Polling mask to use
    MASK = select.POLLIN

    #: Size of each read-request
    READ_SIZE = 4096

    #: Index of last line returned to a caller
    idx = None

    #: Input buffer of incomplete lines
    strbuffer = None

    #: Complete lines, in order received
    lines = None

    def __init__(self, infd, log_fn=None):
        self.idx = -1
        self.strbuffer = ''
        self.lines = []
        self._infd = infd
        self._poll = select.poll()
        self._poll.register(infd, self.MASK)
        self.log_fn = log_fn

    def __str__(self):
        return ''.join(self.lines) + self.peek()

    def _read_stdio(self):
        """Non-blocking read into strbuffer"""
        # Only attempt reading if it will not block
        fd_event_list = self._poll.poll(10)  # milliseconds
        if len(fd_event_list) == 1:
            _fd, event = fd_event_list.pop()
            del _fd  # not needed
        else:
            return 0  # More than 1 fd registered will timeout down-stack.
        if event & self.MASK:
            newoutput = os.read(self._infd, self.READ_SIZE)
        else:
            return 0  # Read would block
        if newoutput != '':
            # Assume terminal type not handled, strip off escape codes
            newoutput = self.STRIP_REGEX.sub('', newoutput)
            self.strbuffer += newoutput
            if self.log_fn and callable(self.log_fn):
                self.log_fn(newoutput)
            return len(newoutput)
        return 0

    def _integrate(self):
        """Integrate any newly received complete lines into self.lines"""
        n_read = self._read_stdio()  # update buffer
        if n_read == 0:
            return 0
        # Don't integrate partial lines, check each for '\n'
        unseenlines = self.strbuffer.splitlines(True)
        # Give oldest first
        unseenlines.reverse()
        unseenline = self.strbuffer  # May not enter while loop
        while unseenlines:
            unseenline = unseenlines.pop()
            if '\n' in unseenline:
                self.lines.append(unseenline)
            else:
                # last line is incomplete
                break
        if unseenline:  # Incomplete line goes back into buffer
            self.strbuffer = unseenline
        else:  # All lines consumed
            self.strbuffer = ''
        return n_read

    def nextline(self):
        """Return next complete unseen line, or None"""
        n_read = self._integrate()
        end_idx = len(self.lines) - 1
        if end_idx < 0:
            return None
        if self.idx >= end_idx and n_read == 0:
            return None  # nothing new was read
        # Lines exist beyond what has been returned
        if self.idx < end_idx:
            self.idx += 1
            return self.lines[self.idx]
        if self.idx > end_idx:
            raise ValueError("Last seen greater than number received")
        # Nothing unseen has arrived
        return None

    def peek(self):
        """Inspect incomplete-line buffer w/o integrating new I/O"""
        if self.strbuffer:
            if self.log_fn is not None and callable(self.log_fn):
                self.log_fn("(peek) %s" % self.strbuffer)
        return str(self.strbuffer)  # return a copy

    def undo(self, idx):
        """
        Reset last-seen line index BACK to idx (forward will raise ValueError)
        """
        if idx <= self.idx:
            if self.log_fn is not None and callable(self.log_fn):
                for old_idx in xrange(self.idx, idx, -1):
                    self.log_fn("(Undoing) %s"
                                % self.lines[old_idx])
            self.idx = idx
        else:
            raise ValueError("Undo index %d not less than or equal to "
                             "current index of %d" % (idx, self.idx))

    def flush(self):
        """
        Process any new input then return
        """
        self._integrate()


class UnseenlineMatchTimeout(RuntimeError):

    """Exception raised from a ``*Match`` class, on timeout expiration"""

    strfmt = ("%s %s regex. '%s' did not match within %0.4f seconds.")

    def __init__(self, regex, unseenlines, start_context, timeout, peek):
        self.regex = regex
        self.unseenlines = unseenlines
        self.start_context = int(start_context)
        self.end_context = unseenlines.idx
        self.timeout = float(timeout)
        self.peek = bool(peek)
        super(UnseenlineMatchTimeout, self).__init__(str(self))

    def __str__(self):
        if self.peek:
            peeking = "While peeking "
        else:
            peeking = ""
        if self.end_context - self.start_context:
            context = "across %d lines" % self.end_context - self.start_context
        else:
            context = ""
        return (self.strfmt
                % (peeking, context, self.regex.pattern, self.timeout))

    def __nonzero__(self):
        # Regex did not match w/in timeout
        return False


# Can't sub-class a MatchObject since it's a special metaclass
class UnseenlineMatch(object):
    """
    Immutable result of first-match regix to a line within timeout

    :param regex: A RegexObject instance
    :param unseenline: An Unseenlines instance
    :param timeout: Maximum time to wait for a match (in seconds)
    :param otherone: (optional) Other Unseenlines instance to flush().
                     Required if one ``unseenline`` depends on another
                     not blocking.
    :raises UnseenlineMatchTimeout: When timeout expires w/o a match.
    """

    # When matched, the instance of the regular expression used
    regex = None

    # When matched, the instance of Unseenlines used
    unseenlines = None

    # When matched, the value of timeout used
    timeout = None

    # When matched, the value of unseenlines.idx just before/after searching
    start_context = None
    end_context = None

    # When matched, list of all the lines searched
    context = None

    def __new__(cls, regex, unseenlines, timeout, otherone=None):
        new_instance = super(UnseenlineMatch, cls).__new__(cls)
        new_instance.start_context = start_context = unseenlines.idx
        xcept = cls.nomatch_xcept(regex, unseenlines, start_context, timeout)
        start = time()
        # Record of all lines searched
        new_instance.context = unseenline = [cls.gather(unseenlines)]
        # Guarantee one-trip through loop
        found = False
        while not found:
            found = cls.match_or_raise(regex, unseenlines, unseenline,
                                       timeout, start, xcept, otherone)
        # No exception was raised
        new_instance.end_context = unseenlines.idx
        return new_instance

    def __init__(self, regex, unseenlines, timeout, otherone=None):
        self.regex = regex
        self.unseenlines = unseenlines
        self.timeout = timeout
        self.otherone = otherone

    def __nonzero__(self):
        return self.unseenlines is not None

    def __str__(self):
        return ("Regex '%s' matched output line %d: '%s'"
                % (self.regex.pattern, self.end_context,
                   # Cheap way of escaping special characters
                   (self.context[-1],)))

    @classmethod
    def nomatch_xcept(cls, regex, unseenlines, start_context, timeout):
        """
        Returns exception instance to be used when no match is found
        """
        return UnseenlineMatchTimeout(regex, unseenlines,
                                      start_context,
                                      timeout, False)

    # Primary, generalized method simply requires many arguments
    # to support descendent classes.
    @classmethod
    def match_or_raise(cls, regex, unseenlines,  # pylint: disable=R0913
                       unseenline, timeout, start, xcept, otherone):
        """
        Helper for __new__, either matches regex or raises xcept

        :param regex: Regular expression object
        :param unseenlines: instance of UnseenLines to search
        :param unseenline: List of already searched lines
        """
        # While there are unseen lines
        while unseenline[-1] is not None:
            if otherone is not None:
                otherone.flush()
            if cls.timedout(start, timeout):
                raise xcept
            found = cls.is_found(regex, unseenline[-1])
            if found:
                # Don't gather the next line
                break
            unseenline.append(cls.gather(unseenlines))
        else:  # every time unseenline is none
            # No guarantee _any_ new lines came in
            if cls.timedout(start, timeout):
                raise xcept
            # Safe to gather (takes time), don't store big list of None
            unseenline[-1] = cls.gather(unseenlines)
            found = False
        return found

    @classmethod
    def timedout(cls, start, timeout):
        """Returns True if timeout has been exceeded"""
        now = time()
        timeout = float(timeout)
        start = float(start)
        return bool(now > start + timeout)

    @classmethod
    def gather(cls, unseenlines):
        """Returns the next string so far unseen from unseenlines"""
        return unseenlines.nextline()

    @classmethod
    def is_found(cls, regex, subject):
        """
        Return True/False on match subject with regex
        """
        return bool(regex.search(subject))


class UnseenlineMatchPeek(UnseenlineMatch):
    """Similar to UnseenlineMatch except it also examines partial lines"""

    @classmethod
    def nomatch_xcept(cls, regex, unseenlines, start_context, timeout):
        """
        Returns exception instance to be used when no match is found
        """
        return UnseenlineMatchTimeout(regex, unseenlines,
                                      start_context,
                                      timeout, True)

    @classmethod
    def gather(cls, unseenlines):
        """Returns the next string so far unseen from unseenlines"""
        nextline = unseenlines.nextline()
        if nextline is None and unseenlines.peek() != '':
            # Current-state only, does NOT gather new I/O
            return unseenlines.peek()
        # Could be None
        return nextline


class NoUnseenlineMatch(UnseenlineMatch):
    """Negative UnseenlineMatch, stuffs non-match back into buffer."""

    def __new__(cls, regex, unseenlines, timeout, otherone=None):
        try:
            return super(NoUnseenlineMatch, cls).__new__(cls, regex,
                                                         unseenlines, timeout)
        except UnseenlineMatchTimeout, xcept:
            # Restore unseenlines context
            xcept.unseenlines.undo(xcept.start_context)
            raise

    def __init__(self, regex, unseenlines, timeout, otherone=None):
        super(NoUnseenlineMatch, self).__init__(regex, unseenlines,
                                                otherone, timeout)
        # Reset unseenline instance back to starting context
        self.unseenlines.undo(self.start_context)

    @classmethod
    def nomatch_xcept(cls, regex, unseenlines, start_context, timeout):
        nlmto = UnseenlineMatchTimeout(regex, unseenlines,
                                       start_context,
                                       timeout, False)
        # No need for a new class just to change the error string
        nlmto.strfmt = ("%s %s regex. '%s' matched unexpectedly "
                        "in %0.4f seconds.")
        return nlmto

    @classmethod
    def is_found(cls, regex, subject):
        """
        Return True/False on non-match subject with regex
        """
        mobj = regex.search(subject)
        return bool(mobj)
