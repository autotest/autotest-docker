#!/usr/bin/env python

import sys
from ConfigParser import SafeConfigParser

scp = SafeConfigParser()

if __name__ == "__main__":
    section = sys.argv[1]
    key = sys.argv[2]
    scp.read(sys.argv[3:])
    print scp.get(section, key)
