"""
Summary
-------

Special scenario - kill stopped container

Operational Summary
-------------------

1. start container with test command
2. stop the container using kill -SIGSTOP
3. send all (safe) signals except SIGCONT
4. send SIGCONT
5. check received signals
"""

from kill_utils import kill_check_base
from dockertest import subtest


class kill_stopped(subtest.SubSubtestCaller):

    """ Subtest caller """


class sigstop(kill_check_base):
    pass


class sigstop_ttyoff(sigstop):

    """ Non-tty variant of the sigstop test """
    tty = False


class sigstop_sigproxy_ttyoff(sigstop):

    """ Non-tty variant of the sigstop_sigproxy test """
    tty = False
