from stress import stress


class attach_sigproxy_stress(stress):

    """
    Tests handling of docker attach --sig-proxy=true (lots of various kills
    and then check)

    initialize:
    1) start VM with test command
    2) create sequence of signals and prepare bash script, which executes them
       quickly one by one.
    run_once:
    3) executes the bash script, which executes series of kills quickly.
    4) sends docker kill -9 and verifies docker was killed
    postprocess:
    5) analyze results
    """
    pass
