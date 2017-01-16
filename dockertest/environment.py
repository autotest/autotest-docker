#!/usr/bin/env python

"""
Low-level/standalone host-environment handling/checking utilities/classes/data

:Note: This module must _NOT_ depend on anything in dockertest package or
       in autotest!
"""

import sys
import errno
import subprocess
try:
    # TODO: Get python-selinux module working in travis (ubuntu)
    import selinux
except ImportError:
    # This always fails on travis with: no get in xattr (E0611)
    # dispite successful 'pip install pyxattr==0.5.1'.  A test
    # for this name has been added to .travis.yml directly.
    from xattr import get as getxattr  # pylint: disable=E0611


# FIXME: pwd is misleading, it should be 'path'
def set_selinux_context(pwd, context=None, recursive=True):
    """
    When selinux is enabled it sets the context by chcon -t ...
    :param pwd: target directory
    :param context: desired context (svirt_sandbox_file_t by default)
    :param recursive: set context recursively (-R)
    :raise OSError: In case of failure
    """
    if context is None:
        context = "svirt_sandbox_file_t"
    if recursive:
        flags = 'R'
    else:
        flags = ''
    # changes context in case selinux is supported and is enabled
    _cmd = ("type -P selinuxenabled || exit 0 ; "
            "selinuxenabled || exit 0 ; "
            "chcon -%st %s %s" % (flags, context, pwd))
    cmd = subprocess.Popen(_cmd, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, shell=True)
    if cmd.wait() != 0:
        raise OSError("Fail to set selinux context by '%s' (%s):\nSTDOUT:\n%s"
                      "\nSTDERR:\n%s" % (_cmd, cmd.poll(), cmd.stdout.read(),
                                         cmd.stderr.read()))


def get_selinux_context(path):
    """
    When selinux is enabled, return the context of ``path``
    :param path: Full or relative path to a file or directory
    :return: SELinux context as a string or None if not set
    """
    try:
        if 'selinux' in sys.modules:
            # First list item is null-terminated string length
            return selinux.getfilecon(path)[1]
        else:
            # may include null-termination in string
            return getxattr(path, 'security.selinux').replace('\000', '')
    except (IOError, OSError), xcpt:
        if xcpt.errno in [errno.EOPNOTSUPP, errno.ENOENT]
            return None
        else:
            raise
