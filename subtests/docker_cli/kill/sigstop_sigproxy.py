"""
Sigstop test (direct kill variant)
"""
from sigstop import sigstop


class sigstop_sigproxy(sigstop):

    """
    Test usage of docker 'kill' command (stopped container)

    initialize:
    1) start VM with test command
    2) create sequence of signals in this manner (uses numeric values):
       [SIGSTOP, 1, 2, 3, .., 8, 10, .., 16, SIGSTOP, 20, .., 31, SIGCONT, 9]
    run_once:
    3) execute series of kill signals followed with the output check
    3b) in case of SIGSTOP it stores following signals until SIGCONT and
        verifies they were all handled properly
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """

    pass
