#!/usr/bin/env python

import os
import sys
from subprocess import Popen, PIPE, STDOUT


def get_envcheck_ignore(what):
    csv = os.environ.get(what)
    if csv is not None:
        return [val.strip() for val in csv.strip().split(',')]
    else:
        return []


def get_docker_path():
    docker_path = os.environ.get('docker_path')
    if docker_path is not None:
        return docker_path
    else:
        return "docker"

def cmdstdout(cmd):
    popen = Popen(cmd, bufsize=1, stdout=PIPE, shell=True, close_fds=True)
    stdoutdata, _ = popen.communicate()
    if popen.returncode != 0:
        print ("Unexpected returncode %d from command %s"
               % (popen.returncode, cmd))
        sys.exit(1)
    return stdoutdata

if __name__ == "__main__":
    ignore_cnames = get_envcheck_ignore('envcheck_ignore_cnames')
    ignore_cids = get_envcheck_ignore('envcheck_ignore_cids')

    cmd = "%s ps -aq" % get_docker_path()
    cids = [line.strip()
            for line in cmdstdout(cmd).strip().splitlines()]
    cnames = []
    cmd = ("%s inspect --format='{{.Name}}' %s"
           % (get_docker_path(), "%s"))
    for cid in cids:
        name = cmdstdout(cmd % cid).strip()
        if name.startswith('/'):
            cnames.append(name[1:])
        else:
            cnames.append(name)
    going_to_fail = False
    for cid, cname in dict(zip(cids, cnames)).iteritems():
        if cid in ignore_cids or cname in ignore_cnames:
            continue
        else:
            going_to_fail = True
            print "%s(%s)" % (cname, cid[0:12]),
    if going_to_fail:
        sys.exit(5)
