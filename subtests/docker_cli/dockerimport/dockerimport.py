r"""
Summary
----------

Exercize multiple variations of the docker import command.
The ``empty`` sub-subtest verifies an empty tarball can be
imported through a pipe.  The ``truncated`` sub-subtest checks
that a tarbal which abruptly ends, results in an error while
importing through a pipe.

Operational Summary
---------------------

#. Create a tarball
#. Pipe tarball into a docker command
#. Check for expected result of docker command

Prerequisites
-----------------

*  The ``tar``, and ``cat`` commands exist in ``$PATH``
"""

from dockertest.subtest import SubSubtestCallerSimultaneous


class dockerimport(SubSubtestCallerSimultaneous):
    pass
