from kill import kill_check_base


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
    pass
