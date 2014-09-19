r"""
Summary
----------

Tests that check output/behavior of ``docker run`` wuth ``-m`` and
``-c`` parameters.  It verifies that the container's cgroup resources
match value passed and if the container can handle invalid values
properly.

Operational Summary
----------------------


Prerequisites
------------------------------------------
*  Docker daemon is running and accessible by it's unix socket.
*  cgroups subsystem enabled, working, and mounted under standard /sys
   location

Configuration
------------------------------------------
*  The option ``expect_success``, sets the pass/fail logic for results
    processing.
*  The option ``memory_value``, sets a quantity of memory to check
*  The ``cpushares_value`` option sets the additional CPU priority
   given to the contained process.
*  Invalid range testing uses the options ``memory_min_invalid`` and
   ``memory_max_invalid``.
*  ``cgroup_path`` will have the container's CID appended, and the value
   from the file specified in option ``cgroup_key_value`` will be checked.
"""

from dockertest.subtest import SubSubtestCallerSimultaneous
from cpushares import cpu_base
from memory import memory_base


class run_cgroups(SubSubtestCallerSimultaneous):
    pass


class cpu_positive(cpu_base):
    pass


class cpu_zero(cpu_base):
    pass


class cpu_none(cpu_base):
    pass


class memory_positive(memory_base):
    pass


class memory_no_cgroup(memory_base):
    pass


class memory_negative(memory_base):
    pass
