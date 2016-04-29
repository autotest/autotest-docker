"""
Parse docker timestamps
"""

import re
import datetime


# This class inherits a LOT of public methods, but most of what
# appears here is all 'behind the scenes' stuff for producing
# immutable instances.
class DockerTime(datetime.datetime):  # pylint: disable=R0903

    """
    Immutable Docker specialized zulu-time representation

    :note: value is undefined when instance == instance.tzinfo.EPOCH.
           For example, the FinishedAt time of a still-running container
    :param isostr: ISO 8601 format string
    :param sep: Optional separation character ('T' by default)
    :raise: ValueError if isostr is unparseable
    """

    class UTC(datetime.tzinfo):

        """Singleton representation of UTC timezone and epoch point"""

        #: Zero timedelta offset
        ZERO = datetime.timedelta(0)

        #: Representation of the beginning of time, created in __new__()
        EPOCH = datetime.datetime(year=1, month=1, day=1,
                                  hour=0, minute=0, second=0,
                                  microsecond=0)

        #: Reference to the singleton instance
        singleton = None

        def __new__(cls):
            if cls.singleton is None:
                cls.singleton = super(DockerTime.UTC, cls).__new__(cls)
                cls.EPOCH = cls.EPOCH.replace(tzinfo=cls.singleton)
                # Not an invalid attribute name, this is a constant
                # value that requires one update to reach it's final
                # form.
                cls.singleton.EPOCH = cls.EPOCH  # pylint: disable=C0103
            return cls.singleton

        @classmethod
        def utcoffset(cls, dt):
            del dt  # not needed
            return cls.ZERO

        @classmethod
        def tzname(cls, dt):
            del dt  # not needed
            return "UTC"

        @classmethod
        def dst(cls, dt):
            del dt  # not needed
            return cls.ZERO

    class UTCOffset(datetime.tzinfo):

        """Fixed offset in hours and minutes from UTC."""

        def __init__(self, offset_string):
            super(DockerTime.UTCOffset, self).__init__()
            numbers = offset_string.split(':')
            hours = int(numbers[0])
            minutes = int(numbers[1])
            self.__offset = datetime.timedelta(hours=hours, minutes=minutes)
            self.__name = "UTC%s" % offset_string

        def utcoffset(self, dt):
            del dt  # not used, but specified in base
            return self.__offset

        def tzname(self, dt):
            del dt  # not used, but specified in base
            return self.__name

        def dst(self, dt):
            del dt  # not used, but specified in base
            return DockerTime.UTC.ZERO

    def __new__(cls, isostr, sep=None):
        if sep is None:
            sep = 'T'
        # datetime can output zulu time but not consume it.
        base = "%s%s%s" % (r"(\s*\d{4})-(\d{2})-(\d{2})",
                           sep,
                           r"(\d{2}):(\d{2}):(\d{2})")
        keys = ['year', 'month', 'day',
                'hour', 'minute', 'second']
        values = []
        # Order is significant, some parsers depend on one-another
        parsers = [cls.__new_tzoffset__, cls.__new_zulu__, cls.__new_us__]
        for parser in parsers:
            if parser(isostr, base, values, keys, cls.UTC()):
                break  # Parsers return True on success
        if values == []:  # No parser was succesful
            raise ValueError("Malformed date time string %s" % isostr)
        # Convert any strings into integers
        for index, value in enumerate(values):
            if isinstance(value, basestring):
                values[index] = int(value)
        dargs = dict(zip(tuple(keys), tuple(values)))
        return super(DockerTime, cls).__new__(cls, **dargs)

    def __repr__(self):
        return '{0}("{1:%Y-%m-%dT%H:%M:%S}.{2:06d}{1:%z}")'.format(
            self.__class__.__name__, self, self.microsecond)

    @classmethod
    def __new_zulu__(cls, isostr, base, values, keys, tzn):
        # Killall letter Z and z's
        isostr.replace('z', ' ')
        isostr.replace('Z', ' ')
        # may or may not have fractional seconds
        has_us = cls.__new_us__(isostr, base, values, keys, tzn)
        if has_us:
            return True
        else:
            regex = re.compile(base)
            mobj = regex.search(isostr)
            if mobj:
                values += list(mobj.groups())
                keys.append('tzinfo')
                values.append(tzn)
                return True
            return False

    @classmethod
    def __new_us__(cls, isostr, base, values, keys, tzn):
        # Try with interpreted microseconds
        regex = re.compile(base + r"\.(\d+)")
        mobj = regex.search(isostr)
        if mobj:
            values += list(mobj.groups())
            # Convert seconds decimal fraction into microseconds
            sec_frac = float("0.%s" % values[-1])
            values[-1] = int(sec_frac * 1000000)
            keys.append('microsecond')
            values.append(tzn)
            keys.append('tzinfo')
            return True
        return False

    @classmethod
    def __new_tzoffset__(cls, isostr, base, values, keys, tzn):
        # Check if ends with +/-00:00 timezone offset, optional
        # non-capturing seconds-fraction parsed by __new_us__()
        regex = re.compile(base + r"(?:\.(\d+))?([+-]{1}\d{2}:\d{2})")
        mobj = regex.search(isostr)
        if mobj:
            tzn = cls.UTCOffset(mobj.group(8))
            # Remove timezone from string, attempt parsing with __new_us__
            isostr = isostr[0:len(isostr) - len(mobj.group(8))]
            return cls.__new_us__(isostr, base, values, keys, tzn)
        return False

    def is_undefined(self):
        """
        Return True if this instance represents an undefined date & time
        """
        return self - self.UTC.singleton.EPOCH == self.UTC.ZERO
