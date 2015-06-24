"""
Module for standardized API version number processing/checking

`Subtest modules`_ code, configuration, and documentation are critical
to remain in agreement in order to support use of external/private or
customized configurations and tests.  Therefor  version checking is
very important. Each subtest must inherit the default 'config_version'
option with the version string of the dockertest API it was written
against.  This may come from ``config_defaults/defaults.ini`` or
``config_custom/defaults.ini`` if it has been customized.  Further,
the documentation version in the top-level ``conf.py`` module must
also match (less the REVIS number).
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import sys
import os.path
import logging
# FIXME: incorrectly missing in Travis CI, disable warning until fixed
from distutils.version import LooseVersion  # pylint: disable=E0611,F0401

import xceptions

#: Major API version number, as an integer (range 0-255).
MAJOR = 0

#: Minor API version number, as an integer (range 0-255).
MINOR = 8

#: API Revision number, as an integer (range 0-255).  Not significant!
#: for version comparisons. e.g. ``0.0.1 == 0.0.2 != 0.2.2``
REVIS = 4

#: String format representation for MAJOR, MINOR, and REVIS
FMTSTRING = "%d.%d.%d"

#: String representation of MAJOR, MINOR, and REVIS using FMTSTRING
STRING = (FMTSTRING % (MAJOR, MINOR, REVIS))

#: If no subtest configuration could be loaded, use this value
#: to signal version checking is impossible
NOVERSIONCHECK = '@!NOVERSIONCHECK!@'

#: If by chance no autotest_version is set, use this value
AUTOTESTVERSION = '0.16.0'

#: Absolute path to directory containing this module
MYDIR = os.path.dirname(sys.modules[__name__].__file__)

#: Parent directory of directory containing this module
PARENTDIR = os.path.dirname(MYDIR)


def str2int(version_string):
    """
    Convert an 'x.y.z' string into binary form
    """
    version_tuple = tuple(int(num) for num in version_string.split('.'))
    assert len(version_tuple) == 3
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
    return FMTSTRING % (major, minor, revis)


# for private, internal-use only
def _bincmp(lhs, rhs):  # pylint: disable=C0111
    no_lrevis = lhs & 0xFFFF00  # mask off upper 24 bits and lower 8 bits
    no_rrevis = rhs & 0xFFFF00
    return cmp(no_lrevis, no_rrevis)


# for private, internal-use only
def _tupcmp(lhs, rhs):  # pylint: disable=C0111
    lhs_bin = lhs[0] << 16 | lhs[1] << 8 | lhs[2]
    rhs_bin = rhs[0] << 16 | rhs[1] << 8 | rhs[2]
    return _bincmp(lhs_bin, rhs_bin)


# for private, internal-use only
def _strcmp(lhs, rhs):  # pylint: disable=C0111
    lhs_split = tuple(int(num) for num in lhs.split('.'))
    rhs_split = tuple(int(num) for num in rhs.split('.'))
    assert len(lhs_split) == 3
    assert len(rhs_split) == 3
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


def get_doc_version():
    """
    Parse version string from conf.py module w/o importing it.

    :return: None on error, string version number of success
    """
    version = None
    # Prevent documentation-generation mocks from clashing with testing
    for line in open(os.path.join(PARENTDIR, 'conf.py'), 'rb'):
        if line.startswith('version ='):
            version = line.split("'")[1]
            return version
    return None


def check_doc_version():
    """
    Compare Dockertest API version to documentation version, fail if greater
    """
    doc_version = get_doc_version()
    msg = ("Dockertest API version %s is greater than "
           "documentation version %s" % (STRING, doc_version))
    # OK if docs are later version than API
    if compare(STRING, doc_version) < 0:
        raise xceptions.DockerVersionError(msg)


def check_version(config_section):
    """
    Simple version check that config version == library version

    *Note:* Ignores REVIS, only MAJOR/MINOR compared.

    :raise DockerVersionError: if Major/Minor don't match
    """
    config_version = config_section.get('config_version', NOVERSIONCHECK)
    if config_version == NOVERSIONCHECK:
        logging.warning("Could not check configuration version matches subtest"
                        " API version.  No 'config_version' option specified "
                        "in configuration")
    else:
        try:
            if compare(config_version, STRING) != 0:
                raise xceptions.DockerVersionError(STRING, config_version)
        except xceptions.DockerVersionError:  # it's a ValueError subclass
            raise
        except (ValueError, TypeError):
            raise xceptions.DockerVersionError(STRING, '<not set for test>')
        except AssertionError:
            raise xceptions.DockerValueError("Internal version comparison "
                                             "problem comparing '%s' to '%s'."
                                             % (str(config_version),
                                                str(STRING)))


def check_autotest_version(config_section, installed_version):
    """
    Raise exception if configured ``autotest_version`` < installed_version
    """
    cfg_version_string = config_section.get('autotest_version', '0.15.0')
    if cfg_version_string == NOVERSIONCHECK:
        return
    cfg_version = LooseVersion(cfg_version_string)
    inst_version = LooseVersion(installed_version)
    if inst_version < cfg_version:
        raise xceptions.DockerVersionError(str(inst_version), str(cfg_version))
