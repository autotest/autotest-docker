#!/usr/bin/env python

"""Simple utility to extract a value from a set of ini-files"""

import sys
from ConfigParser import SafeConfigParser

scp = SafeConfigParser()

if __name__ == "__main__":
    section = sys.argv[1]
    key = sys.argv[2]
    scp.read(sys.argv[3:])
    print scp.get(section, key)
