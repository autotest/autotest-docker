r"""
Summary
----------

Tests that check output/behavior of ``docker run`` wuth ``-m`` and
``-c`` parameters.  It verifies that the container's cgroup resources
match value passed and if the container can handle invalid values
properly.

Operational Summary
----------------------

#. Start container with non-default cgroup-related option.
#. Verify docker inspect matches param value matches actual cgroup value

Prerequisites
------------------------------------------
*  Docker daemon is running and accessible by it's unix socket.
*  cgroups subsystem enabled, working, and mounted under standard /sys
   location
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


class cpu_overflow(cpu_base):
    pass


class memory_positive(memory_base):
    pass


class memory_no_cgroup(memory_base):
    pass


class memory_negative(memory_base):
    pass
