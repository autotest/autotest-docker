"""
Base classes and mechanisms for cgroups testing
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
