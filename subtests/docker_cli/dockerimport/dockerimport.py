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
*  Enough disk space to construct and import several base images
   at the same time.
*  The ``tar``, and ``cat`` commands exist in ``$PATH``

Configuration
----------------

*  The ``image_name_prefix`` and ``image_name_postfix`` specify
   values used to automatically generate a unique image name.
   The unique part will be sandwiched in-between these options
   values.
*  ``try_remove_after_test`` is exactly like the same option in
   the `docker_cli/build sub-test`_ subtest.
*  The ``test_subsubtest_postfixes`` contains a CSV listing of the
   sub-sub-test modules (and class) names to run (in order).
"""

from dockertest.subtest import SubSubtestCallerSimultaneous


class dockerimport(SubSubtestCallerSimultaneous):
    pass
