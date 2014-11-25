#!/usr/bin/env python

import os
import sys
from subprocess import Popen, PIPE, STDOUT


def get_docker_path():
    docker_path = os.environ.get('docker_path')
    if docker_path is not None:
        return docker_path
    else:
        return "docker"

if __name__ == "__main__":
    cmd = "%s images" % get_docker_path()
    popen = Popen(cmd, bufsize=1, stdout=PIPE, shell=True, close_fds=True)
    stdoutdata, _ = popen.communicate()
    if popen.returncode != 0:
        print ("Unexpected returncode %d from command %s"
               % (popen.returncode, cmd))
        sys.exit(1)
    lines = stdoutdata.strip().splitlines()
    if lines[0].startswith('REPOSITORY'):
        del lines[0]
    else:
        print ("Unexpected output line: %s" % lines[0])
        sys.exit(2)
    going_to_fail = False
    for line in lines:
        if '<none>' in line.lower():
            print "Orphan: '%s' ", line.strip.split()[2]
            going_to_fail = True
    if going_to_fail:
        sys.exit(3)
