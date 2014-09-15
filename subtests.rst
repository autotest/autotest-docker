``docker_cli/version`` Sub-test
=================================

Simple test that checks the output of the ``docker version`` command.

``docker_cli/build`` Sub-test
==============================

Tests the ``docker build`` command operation with a set of options
and pre-defined build-content.

``subsubtests = local_path,https_file,git_path``

(``*_path`` means directory, which contains Dockerfile and required files,
 ``*_file`` means direct path to the Dockerfile without other dependencies)

``docker_cli/build`` Prerequisites
------------------------------------------

*  Tarballs bundled with the subtest
*  Statically linked 'busybox' executable available over HTTP

``docker_cli/build`` Configuration
-------------------------------------------

*  The ``docker_build_options`` option specifies additional arguments
   to add in addition to the ``DEFAULTS`` option ``docker_options``.
*  The ``build_timeout_seconds`` option specifies a fixed time (in
   seconds) the build must complete within)
*  ``try_remove_after_test`` is a boolean option, selecting whether
   or not the built-image should be removed when the test is complete.
   (Any removal errors will be ignored)
*  Both the ``image_name_prefix`` and ``image_name_postfix`` behave
   exactly like the `docker_cli/dockerimport sub-test`_ test.
*  The location of the statically linked ``busybox`` executable
   is specified by the ``busybox_url`` option.
*  Source path of Dockerfile or directory containing Dockerfile is defined
   by ``dockerfile_path``

``docker_cli/build_paths`` Sub-test
======================================

Tests the ``docker build`` against a list of docker build paths or git
locations.

``docker_cli/build_paths`` Prerequisites
------------------------------------------

*  Valid docker build paths or git locations with a Dockerfile

``docker_cli/build_paths`` Configuration
-------------------------------------------

*  ``build_paths`` is a csv list of docker build paths or
   git locations.  Paths may be relative to the subtest's directory
   or absolute.  They will copied, and the base image (``FROM`` line) updated
   based on the standard ``docker_repo_name``, ``docker_repo_tag``
   ``docker_registry_host``, and ``docker_registry_user`` options.
*  ``build_args`` are args passed directly to ``docker build``.
*  ``image_repo_name`` lets you name the ``REPOSITORY`` of the images built.
   Only applies if ``--tag`` is not used in ``build_args``
*  ``image_tag_postfix`` lets you add a postfix to the randomly generated
   ``TAG`` of the images built. Only applies if ``--tag`` is not
   used in ``build_args``.

``docker_cli/dockerimport`` Sub-test
=======================================

This test is actually composed of a number of sub-sub-tests.
It demonstrates and supports executing multiple variations
of a test for the same docker-command.  Here, the test is named
``dockerimport`` because ``import`` is a python-keyword.

The sub-sub-tests run somewhat in parallel, with the order
fixed by a configuration option.  This means all sub-sub-test's
``run_once()`` methods will be called first before each
sub-sub-test's ``postprocess()`` methods.  All sub-sub-tests
``cleanup()`` methods are guaranteed to run, even if an
exception or error occurs.

``docker_cli/dockerimport`` Prerequisites
---------------------------------------------

*  Enough disk space to construct and import several base images
   at the same time.
*  The ``tar``, and ``cat`` commands.

``docker_cli/dockerimport`` Configuration
-------------------------------------------

Configuration for this subtest consists of a few options which
control overall sub-sub-test execution.  Further, unique sections
for each sub-sub-test are also used.

*  The ``image_name_prefix`` and ``image_name_postfix`` specify
   values used to automatically generate a unique image name.
   The unique part will be sandwiched in-between these options
   values.

*  ``try_remove_after_test`` is exactly like the same option in
   the `docker_cli/build sub-test`_ subtest.

*  The ``test_subsubtest_postfixes`` contains a CSV listing of the
   sub-sub-test modules (and class) names to run (in order).

*  The sub-sub-test section options are self-explanatory.  For this
   class of sub-test they list the tar-command location and options
   to use before sending the content into the docker import command.


``docker_cli/images_all`` Sub-test
=================================

Checks the difference between ``docker images`` and ``docker images --all``.

``subsubtests`` = two_images_with_parents

``docker_cli/images_all/two_images_with_parents`` Subsub-test
-----------------------------------------------------

#.  Create image test_a
#.  Create image test_a1 with parent test_a
#.  Create image test_b
#.  Create image test_b1 with parent test_b
#.  Untag test_a
#.  Untag test_a1 (verify intermediary images were removed too)
#.  Untag test_b1 (verify test_b was preserved)

*  Between steps 4-7 verify `docker images` and `docker history`


``docker_cli/images`` Sub-test
=======================================

Ultra-simple test to confirm output table-format of docker CLI
'images' command.

``docker_cli/run_volumes`` Sub-test
=======================================

*  volumes_rw: Attempt to read, then write a file from a host path volume inside
   a container.  Intended to test NFS, SMB, and other 'remote' filesystem
   mounts.
*  volumes_one_source: Have multiple containers mount a directory and then write
   to files in that directory simultaneously.

``docker_cli/run_volumes`` Prerequisites
---------------------------------------------

*  Remote filesystems are mounted and accessible on host system.
*  Containers have access to read & write files w/in mountpoints

``docker_cli/run_volumes/volumes_rw`` Configuration
----------------------------------------------------
*  The ``host_paths`` and corresponding ``cntr_paths`` are most important.
   They are the host paths and container paths comma-separated values to
   test.  There must be 1:1 correspondence between CSVs of both options.
   The lists must also be the same length.
*  ``run_template`` allows fine-tuning the options to the run command.
*  The ``cmd_template`` allows fine-tuning the command to run inside
   the container.  It makes use of shell-like value substitution from
   the contents of ``host_paths`` and ``cntr_paths``.
*  The ``wait_stop`` option specifies the time in seconds to wait after all
   docker run processes exit.

``docker_cli/run_volumes/volumes_one_source`` Configuration
------------------------------------------------------------
*  The ``num_containers`` is the number of containers to run concurrently.
*  The ``cmd_timeout`` is the timeout for each container's IO command.
*  The ``cntr_path`` is where to mount the volume inside the container.
*  The ``exec_command`` is the command each container should run.  This
   should be an IO command that writes to a file at ${write_path} which will be
   inside the mounted volume.  This command should also take time to allow for
   taking place while the other containers are also writing IO.


``docker_cli/save_load`` Sub-test
=================================

Tests the ``docker save`` and ``docker load`` commands.

#.  prepare image
#.  save image
#.  remove image
#.  load image
#.  check results
#.  (some subsubtests) check content of the image

subsubtests = simple,stressed_load


``docker_cli/rm`` Sub-test
=======================================

Start up a container, run the rm subcommand on it in various ways

``docker_cli/dockerhelp`` Sub-test
=======================================

Several variations of running the dockerhelp command.

``docker_cli/dockerhelp`` Configuration
-------------------------------------------

*  The ``success_option_list`` is a CSV list of docker options
   where a zero-exit code is expected (though a usage message
   may appear)
*  The ``failure_option_list`` is the opposite.


``docker_cli/run_simple`` Sub-test
=====================================

Three simple subsubtests that verify exit status and signal pass-through capability

``docker_cli/run_simple`` Prerequisites
-----------------------------------------

*  Container image with a ``/bin/bash`` shell executable
*  Container image with a ``/bin/true`` executable returning zero
*  Container image with a ``/bin/false`` executable returning non-zero
*  Container image with a ``/bin/date`` executable
*  Accurate (relative to host) timekeeping in container


``docker_cli/run_attach`` Sub-test
=================================

This test checks different ``docker run -a xxx`` variants.

#. Starts `docker run` with defined combination of `-a ...`
   6 variants are executed per each test:
      variants:
        - tty
        - nontty
      variants:
        - stdin (execute bash, put 'ls /\n exit\n' on stdin)
        - stdout (execute ls /)
        - stderr (execute ls /nonexisting/directory/...)
#. Analyze results

subsubtests = none,stdin,stdout,stderr,in_out,in_err,in_out_err,
random_variant,i_none,i_stdin,i_stdout,i_stderr,i_in_out,i_in_err,
i_in_out_err,i_random_variant

subtests with name ``i_*`` are the same test without this prefix only executed
with ``--interactive`` enabled.


``docker_cli/run_sigproxy`` Sub-test
=======================================

Test usage of docker run/attach with/without '--sig-proxy'

``docker_cli/run_sigproxy`` Prerequisites
---------------------------------------------

*  A remote registry server

``docker_cli/run_sigproxy`` Configuration
-------------------------------------------

*  The ``exec_cmd`` modifies the container command
*  The ``wait_start`` is duration of container init
*  The ``kill_signals`` space separated list of signals used in test

``docker_cli/rmi`` Sub-test
=======================================

Several variations of running the rmi command.

``docker_cli/rmi`` Prerequisites
---------------------------------------------

*  Same as `docker_cli/run_simple Prerequisites`_
*  An existing, standard test image to work with.
*  Image on remote registry with 'latest' and some other tag

``docker_cli/rmi`` Configuration
--------------------------------------

*  The ``docker_rmi_force`` option causes sub-subtests to force remove images
*  ``docker_expected_result`` should be "PASS" or "FAIL" to indicate result
   handling behavior of sub-subtests.


``docker_cli/run_env`` Sub-test
=================================

Tests the ``docker run -e xx=yy`` and other env-related features

*  subsubtests = port

``docker_cli/run_env/port`` Sub-subtest
-------------------------------------

#.  Starts server with custom -e ENV_VARIABLE=$RANDOM_STRING and opened port
#.  Starts client linked to server with another ENV_VARIABLE
#.  Booth prints the env as {}
#.  Client sends data to server (addr from env SERVER_PORT_$PORT_TCP_ADDR)
#.  Server prints data with prefix and resends them back with another one.
#.  Client prints the received data and finishes.
#.  Checks if env and all data were printed correctly.


``docker_cli/pull`` Sub-test
=======================================

Several variations of running the pull command against a registry server.

``docker_cli/pull`` Prerequisites
---------------------------------------------

*  A remote registry server
*  Image on remote registry with 'latest' and some other tag

``docker_cli/commit`` Sub-test
=======================================

Several variations of running the commit command

``docker_cli/commit`` Prerequisites
---------------------------------------------

*  A remote registry server
*  Image on remote registry with 'latest' and some other tag

``docker_cli/events`` Sub-test
=======================================

Start up a simple ``/bin/true`` container while monitoring
output from ``docker events`` command.  Verify expected events
appear after container finishes and is removed.

``docker_cli/events`` Prerequisites
---------------------------------------------

*  Historical events exist prior to running test (i.e.
   docker daemon hasn't been restarted in a while)
*  Host clock is accurate, local timezone setup properly.
*  Host clock does not change drastically during test

``docker_cli/events`` Configuration
--------------------------------------

*  ``run_args`` is a CSV list of arguments to the run command
*  ``rm_after_run`` specifies whether or not to use the ``docker rm``
   command after the container finishes.
*  The ``wait_stop`` option specifies time in seconds to wait
   after removing the container, to check events.
*  ``expect_events`` is a CSV of required events for test to pass
*  ``name_prefix`` specifies the container name prefix to use.
   before random characters are added.
*  The ``unparseable_allowance`` setting specifies the number of
   lines with parse errors to allow.
*  The ``remove_after_test`` option controls cleanup after test


``docker_cli/ps_size`` Sub-test
=================================

Verifies the ``docker ps --size` shows correct sizes
``subsubtests`` = simple

``docker_cli/ps_size/simple`` Subsub-test
-----------------------------------------------------
Simple `docker ps -a --size` test.
#.  Create couple of containers, each creates file of given size
#.  Execute docker ps -a --size
#.  Check the sizes are in given limit ($size; 1mb + $limit_per_mb * $size)

``docker_cli/ps_size/simple`` Configuration
--------------------------------------------
*  ``dd_sizes`` is space-separated size increase to test in MB
*  ``dd_cmd`` is the full command to use for increasing the image
   size.  The ``dd_sizes`` values will be broken down as the two
   string subs. for block-size and count.
*  ``limit_per_mb`` Floating point error-factor per megabyte of
   ``dd_sizes`` value to allow.

``docker_cli/psa`` Sub-test
=======================================

Verify the table output and formatting of the ``docker ps -a``
command.

``docker_cli/psa`` Configuration
--------------------------------------

*  The ``wait_stop`` and ``wait_start`` options specify time in seconds to wait
   before/after starting the test container.
*  The ``remove_after_test`` option controls cleanup after test


``docker_cli/tag`` Sub-test
=======================================

Several variations of running the docker tag command

``docker_cli/tag`` Prerequisites
---------------------------------------------

*  None

``docker_cli/tag`` Configuration
--------------------------------------

*  ``tag_force`` specifies use of ``--force`` option
*  The ``tag_repo_name_prefix`` option has random characters appended
   before it is used for tagging.
*  ``docker_expected_result`` option allows changing between positive
   and negative testing.

``docker_cli/stop`` Sub-test
=======================================

Several variations of running the stop command

``docker_cli/stop`` Prerequisites
---------------------------------------------

*  A remote registry server

``docker_cli/stop`` Configuration
--------------------------------------

*  The ``stop_name_prefix`` is prefix of the tested container followed by
   random characters to make it unique.
*  The ``run_options_csv`` modifies the running container options.
*  The ``stop_options_csv`` specifies the stop command options
*  The ``exec_cmd`` modifies the container command
*  The ``stop_duration`` sets the acceptable stop command duration (+-2s)
*  The ``check_stdout`` value is expected output of command for PASS.
*  To verify the value of ``check_stdout`` does NOT appear, set the
   ``check_output_inverted`` option.
*  The required exit code for PASS is specified by ``docker_exit_code``
   otherwise ``0`` is assumed.

``docker_cli/restart`` Sub-test
=======================================

Several variations of running the restart command

``docker_cli/restart`` Prerequisites
---------------------------------------------

*  A remote registry server

``docker_cli/restart`` Configuration
--------------------------------------

*  The ``run_options_csv`` modifies the running container options.
*  The ``restart_options_csv`` modifies the restart command options.
*  The ``stop_options_csv`` specifies the stop command options.
*  The ``exec_cmd`` modifies the container command
*  The ``start_check``, ``restart_check`` and ``stop_check`` are '\n' separated
   lines which should be present in specific test stage.
*  The ``restart_duration`` and ``stop_duration`` are expected command execution
   durations (+-3s)

``docker_cli/start`` Sub-test
=======================================

Several variations of using ``docker start`` command

``docker_cli/start`` Prerequisites
---------------------------------------------

*  A remote registry server

``docker_cli/start`` Configuration
--------------------------------------

*  The ``container_name_prefix`` is prefix of the tested container followed by
   random characters to make it unique.
*  The ``run_cmd`` option
*  Options ``docker_start_timeout`` and ``docker_run_timeout`` specify max
   time to wait for container to start, and finish (``docker wait``).
*  The ``docker_interactive`` and ``docker_attach`` options specify whether
   or not the container is initially run with the ``-i`` and/or ``-d``
   parameters.


``docker_cli/kill`` Sub-test
=======================================

Several variations of running the kill command
*  random_* - series of random signals
*  sigstop - worst case of stopped container scenario
*  bad - bad input
*  stress - lots of signals without waiting
*  stress_parallel - all signals simultaneously
*  run_sigproxy* - instead of ``docker kill`` uses ``kill`` on ``docker run``
*  attach_sigproxy* - instead of ``dicker kill`` uses ``kill`` on ``docker attach``

``docker_cli/kill`` Prerequisites
---------------------------------------------

*  A remote registry server

``docker_cli/kill`` Configuration
--------------------------------------

*  The ``run_container_attached`` - When ``True``, creates detached container
   and uses docker attach process in test.
*  The ``run_options_csv`` modifies the ``docker run`` options.
*  The ``attach_options_csv`` modifies the ``docker attach`` options.
*  The ``exec_cmd`` modifies the container command.
*  ``stress_cmd_timeout`` - maximal acceptable delay caused by stress command
*  The ``wait_start`` is duration of container initialization
*  The ``no_iterations`` is number of signals (in some subsubtests)
*  The ``kill_map_signals`` chooses between numerical and named signals (USR1)
   *  ``true`` - all signals are mapped
   *  ``false`` - all signals are numbers
   *  ``none`` - randomize for each signal
*  The ``signals_sequence`` allows you to force given sequence of signals.
   When none, new one is generated and logged for possible reuse.
*  The ``kill_signals`` specifies used signals ``[range(*args)]``
*  The ``skip_signals`` specifies which signals should be omitted
*  The ``kill_sigproxy`` changes the kill command:
   *  ``false`` -> ``docker kill $name``
   *  `true`` -> ``os.kill $docker_cmd.pid``


``docker_cli/logs_follow`` Sub-test
=================================

This test checks correctness of docker logs --follow

subsubtests = simple*

``docker_cli/logs_follow/simple*``
--------------------------------------------

#.  Start container
#.  Start `docker logs --follow` process
#.  Execute couple of cmds
#.  Start `docker logs` (without --follow) process
#.  Execute couple of cmds (output to stderr)
#.  Stop container
#.  Start `docker logs` (without --follow) process
#.  Check correctness o 2, then compare 2 and 7 (match) and 4 (partial
    match). Also check all exit statuses/errors/...

differences between the variants are different container cmd (tty, attach)


``docker_cli/top`` Sub-test
=======================================

Several variations of running the restart command

``docker_cli/top`` Prerequisites
---------------------------------------------

*  A remote registry server
*  A docker image capable of executing the ``ps`` command

``docker_cli/top`` Configuration
--------------------------------------

*  Customized configuration for ``docker_repo_name``, ``docker_repo_tag``,
   and optionally ``docker_registry_host`` and/or ``docker_registry_user``.
*  The ``container_name_prefix`` is prefix of the tested container followed by
   random characters to make it unique.
*  The ``run_options_csv`` modifies the running container options.


``docker_cli/wait`` Sub-test
=======================================

Several variations of running the restart command

``docker_cli/wait`` Prerequisites
---------------------------------------------

*  A remote registry server

``docker_cli/wait`` Configuration
--------------------------------------

*  The ``run_options_csv`` modifies the running container options.
*  The ``wait_options_csv`` modifies the wait command options.
*  The ``exec_cmd`` modifies the container command. Note that in this tests
   you can specify per-container-exec_cmd using exec_cmd_$container.
   This command has to contain ``exit $NUM``, which is used as docker exit
   status and could contain ``sleep $NUM`` which signals the duration after
   which the container finishes.
*  The ``wait_for`` specifies the containers the wait command should wait for.
   Use index of ``containers`` or ``_$your_string``. In the second
   case the leading character ``_`` will be removed.


``docker_cli/info`` Sub-test
=================================

Simple test that checks the output of the ``docker info`` command.
It verifies the output against values obtained from userspace tools.

``docker_cli/info`` Prerequisites
-------------------------------------

*  Docker daemon is running and accessible by it's unix socket.
*  ``dmsetup`` and ``du`` commands are available.

``docker_cli/info`` Configuration
--------------------------------------

None

``docker_cli/cp`` Sub-test
=================================

Simple tests that check the the ``docker cp`` command.  The ``simple``
subtest verifies content creation and exact match after cp.  The
``every_last`` verifies copying many hundreds of files from a
stopped container to the host.

``docker_cli/cp`` Prerequisites
-------------------------------------

*  Docker daemon is running and accessible by it's unix socket.
*  Docker image with fairly complex, deeply nested directory
   structure.

``docker_cli/cp`` Configuration
---------------------------------

*  The ``name_prefix`` option is used for naming test containers
*  Directory/file prefixes to skip are listed as **quoted** CSV
   to the ``exclude_paths`` option
*  The ``exclude_symlinks`` yes/no option will skip trying to
   copy any files which are symlinks in the container.
*  The ``max_files`` option will stop copying after this many
   files.

``docker_cli/insert`` Sub-test
=================================

Simple test that checks the success of the ``docker insert`` command.
It will insert the file at the url into an image, and then verify that
it was inserted successfully.

``docker_cli/insert`` Prerequisites
-------------------------------------

*  Docker daemon is running and accessible by it's unix socket.

``docker_cli/insert`` Configuration
--------------------------------------

*  The ``file_url`` is the url to a file to be inserted during
   the test.

``docker_cli/run_twice`` Sub-test
=================================

Verify that could not run a container which is already running.

``docker_cli/run_user`` Sub-test
=================================

This test checks correctness of docker run -u ...

#.  get container's /etc/passwd
#.  generate uid which suits the test needs (nonexisting, existing name, uid..)
#.  execute docker run -u ... echo $UID:$GID; whoami
#.  check results (pass/fail/details)

subsubtests = default,named_user,bad_user,bad_number,too_high_number

``docker_cli/diff`` Sub-test
============================

This set of tests modifies files within an image and then
asserts that the changes are picked up correctly by ``docker diff``

``docker_cli/diff`` Prerequisites
---------------------------------

*  Docker daemon is running and accessible by it's unix socket.

``docker_cli/diff`` Configuration
---------------------------------

*  ``command`` is a csv arg list to ``docker run`` that specifies
   how a test will modify a file for the test
*  ``files_changed`` is a csv list of expected change types and the
   files/directories that are changed.  It is in the form of:
   <change type 1>,<path 1>,<change type 2>,<path 2> and so on.

``docker_cli/invalid`` Sub-test
=================================

Simple test that checks the success of the ``docker run`` command.
It will run container using the invalid character, and then verify that
it was not allowed.

``docker_cli/invalid`` Prerequisites
-------------------------------------

*  Docker daemon is running and accessible by it's unix socket.

``docker_cli/invalid`` Configuration
--------------------------------------

*  The ``section`` specifies which section to test.
*  The ``subsubtests`` specifies which subtests to run.

``docker_cli/workdir`` Sub-test
=================================

Simple test that checks the ``docker run --workdir`` command could set workdir
successfully if the dir is a valid path, and fails if it's not absolute path or
not a path, like a file.

``docker_cli/workdir`` Prerequisites
-------------------------------------

*  Docker daemon is running and accessible by it's unix socket.

``docker_cli/workdir`` Configuration
--------------------------------------

*  The ``remove_after_test`` specifies whether to remove the
   container created during the test.

``docker_cli/dockerinspect`` Sub-test
=====================================

This is a set of subsubtests that test the inspect command.

``docker_cli/dockerinspect`` Prerequisites
------------------------------------------

*  Docker daemon is running and accessible by it's unix socket.

``docker_cli/dockerinspect`` Configuration
------------------------------------------

*  The ``remove_after_test`` specifies whether to remove the
   containers created during the test.
*  The ``subsubtests`` tells which subtests to run in this test group.

``docker_cli/dockerinspect/inspect_container_simple`` Configuration
--------------------------------------------------------------------

*  ``check_fields`` specifies which fields to check the existence of when
   running "docker inspect" on a container.

``docker_cli/dockerinspect/inspect_all`` Configuration
------------------------------------------------------

* ``ignore_fields`` specifies which fields to ignore when checking all fields
  when running "docker inspect" on a container.

``docker_cli/dockerinspect/inspect_keys`` Configuration
-------------------------------------------------------
* note all of these fields are optional.  Leave them blank to skip
  checking for them.
* ``image_keys`` specifies which fields to check for in an image inspect
* ``container_keys`` specifies which fields to check for in a container inspect
* ``key_regex`` asserts that each key matches this regex

``docker_cli/run_cgroups`` Sub-test
======================================

Simple tests that check output/behavior of ``docker run`` wuth ``-m`` and
``-c`` parameters.  It verifies that the container's cgroup resources
match value passed and if the container can handle invalid values
properly.

``docker_cli/run_cgroups`` Prerequisites
------------------------------------------

*  Docker daemon is running and accessible by it's unix socket.
*  cgroups subsystem enabled, working, and mounted under standard /sys location

``docker_cli/run_cgroups`` Configuration
------------------------------------------
*  The option ``expect_success``, sets the pass/fail logic for results processing.
*  The option ``memory_value``, sets a quantity of memory to check
*  The ``cpushares_value`` option sets the additional CPU priority
   given to the contained process.
*  Invalid range testing uses the options ``memory_min_invalid`` and
   ``memory_max_invalid``.
*  ``cgroup_path`` will have the container's CID appended, and the value
   from the file specified in option ``cgroup_key_value`` will be checked.


``docker_cli/syslog`` Sub-test
=================================

Simple test that checks monitoring containers logs from host
via bind-mount /dev/log to containers.

``docker_cli/syslog`` Prerequisites
-------------------------------------

*  Docker daemon is running and accessible by it's unix socket.
*  /dev/log is existing and could be mounted to containers.

``docker_cli/syslog`` Configuration
--------------------------------------


``docker_cli/flag`` Sub-test
=================================

Simple test that checks the flag of the ``docker`` command.
It will run container using the flag character, and then verify that
it was not allowed.

``docker_cli/flag`` Prerequisites
-------------------------------------

*  Docker daemon is running and accessible by it's unix socket.

``docker_cli/flag`` Configuration
--------------------------------------
*  The option ``remove_after_test`` specifies whether to remove the
   container created during the test.

``docker_cli/iptable`` Sub-test
===============================

This a set of test that check the container's iptable rules on host.

``docker_cli/iptable`` Prerequisites
------------------------------------

*  Docker daemon is running and accessible by it's unix socket.
*  iptables service is **not** running, nor other services which
   change iptables (like libvirtd).
*  Firewalld daemon is running and does not show any errors about
   fail to add rules (https://bugzilla.redhat.com/show_bug.cgi?id=1101484).
*  Command iptable and brctl are working well.

``docker_cli/iptable`` Configuration
-------------------------------------

*  The option ``name`` sets the container's prefix name.
*  The option ``bash_cmd`` sets the command that the container will execute.

``docker_cli/import_url`` Sub-test
====================================

This a set of tests to verify docker import from a URL

``docker_cli/import_url`` Prerequisites
-------------------------------------------

The configured URL points to a tarball in an accepted format
by docker (plain, bzip, gzip, etc.).

``docker_cli/import_url`` Configuration
-----------------------------------------

*  ``tar_url`` specifies the URL of a tarball to test

``docker_cli/import_url/md5sum`` Sub-test
-------------------------------------------

Simple subtest that copy's a file from imported image and
compares it's md5sum against a known value

``docker_cli/import_url/md5sum`` Configuration
------------------------------------------------

*  The ``name_prefix`` and ``repo_prefix`` are used
   to help identify containers and images outside the test.
*  ``in_tar_file`` specifies the full path to a test file
   contained within the tarball
*  ``md5sum`` specifies the md5sum hash value for the file
   referenced by ``in_tar_file`` option.

``docker_daemon/network`` Sub-test
===============================

This a set of test that check the container's network security.

``docker_daemon/network`` Prerequisites
------------------------------------

*  Docker is installed in host system.
*  Container os has installed python package.
*  Command iptable and brctl are working well.

``docker_daemon/network`` Configuration
-------------------------------------

*  The option ``docker_daemon_args`` sets the special network args.
*  The option ``docker_daemon_bind`` sets special bind address.

``docker_daemon/network/icc`` Subsub-test
-----------------------------------------

Test if inter-container communication works properly.

1. restart daemon with icc=false (forbid communication)
   in network_base.initialize
2. start container1 and get their ip addr
3. Try to connect containers with python
  * Start script for listening

  ::

            python -c 'import socket; s = socket.socket();
                       s.bind(("0.0.0.0", 8081)); w = s.listen(10);
                       w,_ = s.accept(); w.sendall("works");
                       w.close(); s.close()'
  * start container2 and try to connect and recv from container1

  ::

            python -c 'import socket; s = socket.socket();
                       s.connect(("192.168.100.1", 8081)); print s.recv(100);
                       s.close();
4. If python is not found fall back to ping
5. fail if communication pass from container2 to container1

``docker_daemon/network/icc`` Configuration
-----------------------------------------

*  The option ``docker_cmd1_args`` sets args for server container commands.
*  The option ``docker_cmd2_args`` sets args for client container commands.

``docker_daemon/tls`` Sub-test
===============================

This a set of test that check the container's network security.

``docker_daemon/tls`` Prerequisites
------------------------------------

*  Docker is installed in host system.

``docker_daemon/tls`` Configuration
-------------------------------------

*  The option ``docker_daemon_bind`` sets special bind address.
*  The option ``docker_client_bind`` sets special client args.
*  The option ``docker_options_spec`` sets additional docker options.

``docker_daemon/tls/tls_verify_all`` Subsub-test
-----------------------------------------

Test docker tls verification.

#. Create CA certificate
#. Create certificate for daemon
#. Create certificate for client
#. Verify if docker tls verification works properly.

``docker_daemon/tls/tls_verify_only_server`` Subsub-test
-----------------------------------------

Test docker tls connection test check only server identity using ca.crt

*  daemon -d,--selinux-enabled,--tls,--tlscert=server.crt,--tlskey=server.key
*  client %(docker_options)s,--tlsverify,--tlscacert=ca.crt

#. restart daemon with tls configuration
#. Check client connection
#. cleanup all containers and images.

``docker_daemon/tls/tls_verify_server_no_client`` Subsub-test
-----------------------------------------

Test docker tls connection test check only server identity using ca.crt server
do not check wrong certificate from passed from client.

*  daemon --tls,--tlscert=server.crt,--tlskey=server.key
*  client --tlsverify,--tlscacert=ca.crt,--tlscert=wrongclient.crt,--tlskey=wrongclient.key

#. restart daemon with tls configuration
#. Check client connection
#. cleanup all containers and images.

``docker_daemon/tls/tls_verify_wrong_client`` Subsub-test

Test docker tls. Try to connect to server with wrong client certificates.
Client should return exitstatus different from 0 and should contain
"bad certificate" in stderr.

*  daemon --tlsverify,--tlscacert=ca.crt,--tlscert=server.crt,--tlskey=server.key
*  client --tlsverify,--tlscacert=ca.crt,--tlscert=wrongclient.crt,--tlskey=wrongclient.key

#) restart daemon with tls configuration
#) Try to start docker client with wrong certs.
#) Check if client fail.
#) cleanup all containers and images.

-----------------------------------------

``docker_daemon/tls/tls_verify_wrong_server`` Subsub-test
-----------------------------------------

Test docker tls. Try to connect to server which uses wrong certificates with
client good certificates. Client should return exitstatus different from 0 and
should contain "certificate signed by unknown authority" in stderr.

*  daemon --tlsverify,--tlscacert=ca.crt,--tlscert=server.crt,--tlskey=server.key
*  client --tlsverify,--tlscacert=ca.crt,--tlscert=wrongclient.crt,--tlskey=wrongclient.key

#. restart daemon with tls configuration
#. Try to start docker client with wrong certs.
#. Check if client fail.
#. cleanup all containers and images.
