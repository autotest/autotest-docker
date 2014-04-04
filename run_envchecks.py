#!/usr/bin/env python

r"""
**Standalone** Calls to executables in ENVCHECKDIR, reporting all failures.

The [DEFAULTS] section from first loadable ini-file passed in as a parameter
will be passed through as the environment variables to each executable.

:Note: This module must _NOT_ depend on anything in autotest!
"""

import sys
import os.path
# Avoid using dockertest.config, that's only for subtests to use
from ConfigParser import SafeConfigParser
from dockertest.environment import EnvCheck

#: Absolute path to directory containing this module
MYDIR = os.path.dirname(os.path.abspath(sys.modules[__name__].__file__))

ENVCHECKSUBDIR = 'envchecks'

ENVCHECKDIR = os.path.join(MYDIR, ENVCHECKSUBDIR)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print ("Usage: %s CONFIG_FILE [CONFIG_FILE...]\n\nWhere CONFIG_FILE(s) "
               "are ini-style text files containing only a '[DEFAULTS]' "
               "section.\nThe first readable file will be used, any remaining "
               " or unreadable are ignored." % os.path.basename(sys.argv[0]))
        exit(1)
    scp = SafeConfigParser()
    # Stops at first successful load
    scp.read(sys.argv[1:])
    good = EnvCheck(dict(scp.items('DEFAULTS')), ENVCHECKDIR)
    if not good:
        print good
        sys.exit(2)
