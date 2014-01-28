"""
Module for standardized API version number processing/checking

`Subtest modules`_ code, configuration, and documentation are critical
to remain in agreement, therefor version checking is very important.
Each subtest must override the default 'config_version' option with
the version string of the dockertest API it was written against.
Further, the documentation version in the top-level ``conf.py``
module must also match.
"""

import xceptions

#: Major API version number, as an integer (range 0-255).
MAJOR = 0

#: Minor API version number, as an integer (range 0-255).
MINOR = 0

#: API Revision number, as an integer (range 0-255).  Not significant
#: for version comparisons. e.g. ``0.0.1 == 0.0.2 != 0.2.2``
REVIS = 1

#: String format representation for MAJOR, MINOR, and REVIS
FMTSTRING = "%d.%d.%d"

#: String representation of MAJOR, MINOR, and REVIS using FMTSTRING
STRING = (FMTSTRING % (MAJOR, MINOR, REVIS))

def str2int(version_string):
    """
    Convert an 'x.y.z' string into binary form
    """
    version_tuple = tuple(int(num) for num in version_string.split('.'))
    assert len(version_tuple) >= 3
    for num in version_tuple:
        assert num <= 255  # 8-bit cap on all
    version_int = version_tuple[0] << 16
    version_int |= version_tuple[1] << 8
    version_int |= version_tuple[2]
    return version_int & 0xFFFFFF

def int2str(version_int):
    """
    Convert a binary form into an 'x.y.z' string
    """
    assert version_int <= 16777215
    major = (version_int & 0xFF0000) >> 16
    minor = (version_int & 0xFF00) >> 8
    revis = (version_int & 0xFF)
    return (FMTSTRING % (major, minor, revis))

def _bincmp(lhs, rhs):
    no_lrevis = lhs & 0xFFFF00  # mask off upper 24 bits and lower 8 bits
    no_rrevis = rhs & 0xFFFF00
    return cmp(no_lrevis, no_rrevis)


def _tupcmp(lhs, rhs):
    lhs_bin = lhs[0] << 16 | lhs[1] << 8 | lhs[2]
    rhs_bin = rhs[0] << 16 | rhs[1] << 8 | rhs[2]
    return _bincmp(lhs_bin, rhs_bin)


def _strcmp(lhs, rhs):
    lhs_split = tuple(int(num) for num in lhs.split('.'))
    rhs_split = tuple(int(num) for num in rhs.split('.'))
    assert len(lhs_split) >= 3
    assert len(rhs_split) >= 3
    for side in (lhs_split, rhs_split):
        for num in side:
            assert num <= 255  # 8-bit cap on all 3
    return _tupcmp(lhs_split, rhs_split)


def compare(lhs, rhs):
    """
    Compare lhs version to rhs version (ignoring revision number)

    :param lhs: Left-hand-side, string, list, tuple, or number
    :param rhs: Right-hand-side, same type as lhs
    """
    assert isinstance(rhs, lhs.__class__)
    if isinstance(lhs, (str, unicode)):
        return _strcmp(lhs, rhs)
    elif isinstance(lhs, (tuple, list)):
        return _tupcmp(lhs, rhs)
    else:
        raise ValueError("lhs and rhs must both be string, list, "
                         "tuple, or number")

def check_version(config_section):
    """
    Simple version check that config version >= library version

    :raises: dockertest.xceptions.DockerVersionError
    """
    config_version = config_section['config_version']
    if compare(config_version, STRING) < 0:
        raise xceptions.DockerVersionError(STRING, config_version)
