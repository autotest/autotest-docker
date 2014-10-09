"""
Summary
----------

Several variations of running the kill command.

*  random_* - series of random signals
*  run_sigproxy* - instead of ``docker kill`` uses ``kill`` directly on the
   ``docker run`` process
*  attach_sigproxy* - instead of ``docker kill`` uses ``kill`` on
    ``docker attach`` process

Operational Summary
----------------------

1. start container with test command
2. execute docker kill no_iteration times
3. analyze results
"""
from dockertest import subtest
from kill_utils import kill_check_base


class kill(subtest.SubSubtestCaller):

    """ Subtest caller """


class random_num(kill_check_base):

    """
    Test usage of docker 'kill' command (series of random valid numeric
    signals)

    initialize:
    1) start VM with test command
    2) create random sequence of kill signals
    run_once:
    3) execute series of kill signals (NUMERIC) followed with the output check
    3b) in case of SIGSTOP it stores following signals until SIGCONT and
        verifies they were all handled properly
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """


class random_name(kill_check_base):

    """
    Test usage of docker 'kill' command (series of random correctly named
    signals)

    initialize:
    1) start VM with test command
    2) create random sequence of kill signals
    run_once:
    3) execute series of kill signals (NAME) followed with the output check
    3b) in case of SIGSTOP it stores following signals until SIGCONT and
        verifies they were all handled properly
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """


class go_lang_bad_signals(kill_check_base):

    """
    Tests signals, which are not forwarded due of outstanding Golang bug.

    initialize:
    1) start VM with test command
    run_once:
    2) execute specific series of kill signals and checks the output
    postprocess:
    3) analyze results
    """


class run_sigproxy(kill_check_base):

    """
    Tests handling of docker run --sig-proxy=true (series of random valid
    numeric signals)

    initialize:
    1) start VM with test command
    2) create random sequence of kill signals
    run_once:
    3) execute series of kill signals (NUMERIC) followed with the output check
    3b) in case of SIGSTOP it stores following signals until SIGCONT and
        verifies they were all handled properly (ignored)
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """


class attach_sigproxy(kill_check_base):

    """
    Tests handling of docker attach --sig-proxy=true (series of random valid
    numeric signals)

    initialize:
    1) start VM with test command
    2) create random sequence of kill signals
    run_once:
    3) execute series of kill signals (NUMERIC) followed with the output check
    3b) in case of SIGSTOP it stores following signals until SIGCONT and
        verifies they were all handled properly (ignored)
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """


# Add _ttyoff variant for each SubSubtest in this module
new_classes = []
for name, cls in locals().items()[:]:
    try:
        if issubclass(cls, subtest.SubSubtest):
            name = '%s_ttyoff' % name
            new_cls = type(name, cls.__bases__, dict(cls.__dict__))
            new_cls.tty = False
            new_classes.append((name, new_cls))
    except TypeError:   # Not a class
        pass
for name, cls in new_classes:
    globals()[name] = cls
