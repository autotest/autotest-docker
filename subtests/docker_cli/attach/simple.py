"""
Test attach

1) Start docker run --interactive --name=xxx fedora cat
2) Start docker attach xxx
3) Try write to stdin using docker run process (shouldn't pass)
4) Try write to stdin using docker attach process (should pass)
5) check if docker run process get input from attach process.
6) check if docker attach/run process don't get stdin from docker run process.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from attach import simple_base


class simple(simple_base):
    pass
