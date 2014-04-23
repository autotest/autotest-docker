#!/usr/bin/env python

import os
import sys
from subprocess import Popen, PIPE, STDOUT

def get_envcheck_ignore_iids():
    csv = os.environ.get('envcheck_ignore_iids')
    if csv is not None:
        return csv.strip().split(',')
    else:
        return []

def get_envcheck_ignore_fqin():
    csv = os.environ.get('envcheck_ignore_fqin')
    if csv is not None:
        return csv.strip().split(',')
    else:
        return []

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
    ignore = get_envcheck_ignore_iids() + get_envcheck_ignore_fqin()
    lines = stdoutdata.strip().splitlines()
    if lines[0].startswith('REPOSITORY'):
        del lines[0]
    else:
        print ("Unexpected output line: %s" % ignore[0])
        sys.exit(2)
    going_to_fail = False
    for line in lines:
        repo, tag, iid, _ = line.strip().split(None, 3)
        fqin = repo + ':' + tag
        if repo in ignore or fqin in ignore or iid in ignore:
            continue
        else:
            print "%s(%s)" % (fqin, iid),
            going_to_fail = True
    if going_to_fail:
        sys.exit(4)
