.. Docker Autotest documentation master file, created by
   sphinx-quickstart on Tue Feb 18 09:56:35 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. Quick reference for reStructuredText:
   http://docutils.sourceforge.net/docs/user/rst/quickref.html

.. Reference for sphinx.ext.autodoc extenstion:
   http://sphinx-doc.org/ext/autodoc.html

================
Docker Autotest
================

**Warning:** The client-test code here is highly experimental and possibly
temporary. Interfaces/Usage could change, or the entire contents could disappear
without warning.

-------------
Contents
-------------

.. toctree::
   :maxdepth: 2

.. contents:: \

----------------
Introduction
----------------

Docker Autotest_ is a sub-framework for standalone testing of docker_.
It does not strictly depend on docker itself, though it will make use
of the python-docker-py_ package (currently a reference implementation)
if/when available.

It is designed to support extremely simple linear and iterative testing
of arbitrary external commands under control of test-specific and default
configuration values.  Test content and configuration is fully modular,
supporting both bundled and external tests.

As with other `Autotest Client Tests`_ the main entry point is the test
control file.  Docker Autotest's control file utilizes Autotest's
steps-engine.  This allows individual sub-tests and their control,
configuration, and execution state to be stored then retrieved should
a host-kernel panic or userspace become unresponsive.

.. _docker: http://www.docker.io

.. _Autotest: http://github.com/autotest/autotest/wiki

.. _python-docker-py: http://github.com/dotcloud/docker-py#readme

.. _Autotest Client Tests: http://github.com/autotest/autotest-client-tests

----------------
Prerequisites
----------------

*  `Supported Docker OS platform`_

    *  Fedora 20 recommended
    *  Linux kernel 3.12.9 or later

*  Autotest & Autotest Client

    *  Git clone of https://github.com/autotest/autotest.git

                        *or*

    *  Platform-specific binary package (e.g. ``autotest-framework``)

    *  Environment variable ``AUTOTEST_PATH`` set to absolute path where
       autotest installed (if it's *not* in ``/usr/local/autotest``)

*  Core-utils or equivalent (i.e. ``cat``, ``mkdir``, ``tee``, etc.)
*  Tar and supported compression programs
*  Git (and basic familiarity with it's operation)
*  Python 2.4 or greater (but not 3.0)
*  Docker installation (with ``docker -d`` running at startup)
*  (Optional) The python-docker-py_ package for your platform
*  *Any specific requirements for particular* `subtest modules`_

.. _Supported Docker OS platform: https://www.docker.io/gettingstarted/#h_installation

----------------
Quickstart
----------------

#)  Double-check you meet all the requirements in `prerequisites`_.
#)  Within your ``$AUTOTEST_PATH``, change to the ``client`` subdirectory.
#)  Clone the ``docker`` branch of `Docker Autotest Client Tests`_ repository
    into the ``tests`` subdirectory. e.g.
    ``git clone -b docker https://github... tests``
#)  Run the autotest standalone client (``autotest-local``).

.. _Docker Autotest Client Tests: https://github.com/cevich/autotest-client-tests.git


The default behavior is to run all subtests. However, the example below
demonstrates using the ``--args`` parameter to select *only two* sub-tests:

::

    [root@docker ~]# cd $AUTOTEST_PATH
    [root@docker autotest]# cd client

::

    [root@docker client]# git clone -b docker \
         https://github.com/cevich/autotest-client-tests.git tests
    Cloning into 'tests'...
    remote: Reusing existing pack: 12213, done.
    remote: Counting objects: 72, done.
    remote: Compressing objects: 100% (50/50), done.
    remote: Total 12285 (delta 14), reused 61 (delta 12)
    Receiving objects: 100% (12285/12285), 65.61 MiB | 9.05 MiB/s, done.
    Resolving deltas: 100% (8773/8773), done.
    Checking connectivity... done.

::

    [root@docker client]# ./autotest-local run docker --args=example,docker_cli/version
    Writing results to /usr/local/autotest/client/results/default
    START   ----    ----
        START   docker/subtests/example.test_1-of-2
            RUNNING ----    INFO: initialize()
            RUNNING ----    INFO: run_once()
            RUNNING ----    INFO: postprocess_iteration(), iteration #1
            RUNNING ----    INFO: run_once() iteration 2 of 3
            RUNNING ----    INFO: postprocess_iteration(), iteration #2
            RUNNING ----    INFO: run_once() iteration 3 of 3
            RUNNING ----    INFO: postprocess_iteration(), iteration #3
            RUNNING ----    INFO: postprocess()
            RUNNING ----    INFO: cleanup()
            GOOD    docker/subtests/example.test_1-of-2
        END GOOD    docker/subtests/example.test_1-of-2
        START   docker/subtests/docker_cli/version.test_2-of-2
             RUNNING ----    INFO: initialize()
             RUNNING ----    INFO: run_once()
             RUNNING ----    INFO: postprocess_iteration(), iteration #1
             RUNNING ----    INFO: Found docker versions client: 0.7.6 server 0.7.6
             RUNNING ----    INFO: Docker cli version matches docker client API version
             RUNNING ----    INFO: cleanup()
             GOOD    docker/subtests/docker_cli/version.test_2-of-2
        END GOOD    docker/subtests/docker_cli/version.test_2-of-2
    END GOOD    ----    ----
    [root@docker ~]#

(timestamps and extra text removed for clarity)

**Note:** Subtest names are all relative to the ``subtests`` sub-directory and must
be fully-qualified.  e.g. ``docker_cli/version`` refers to the subtest module
``subtests/docker_cli/version/version.py``.

.. _subtests:

------------------
Subtest Modules
------------------

The following sections detail specific sub-tests, their configuration
and any prerequisites or setup requirements.

**Note**: The ``subtest`` directory is *not* setup as a python package
on purpose.  This guaranteese no "accidents" are possible within the
autotest client and that all subtest-state is kept segregated.  However,
any files within the same directory as a subtest module are available
for importing.  The global ``dockertest`` namespace is also available.

Default configuration options
================================

These options exist under the special ``DEFAULTS`` section in the
``config.d/defaults.ini`` file.  Unlike all other sections,
the ``DEFAULTS`` section is global.  All of it's contents will
automatically appear in all other sections, unless overridden.

*  The ``config_version`` option is special.  Because it is part
   of the lower-level `Subtest Module`_ interface, it must exist
   in all sections.  However it's actual value is subtest dependent
   so therefor must also be overridden by each subtest.  The value
   used here is both a reminder and a fail-safe.  Sub-tests that
   neglect to override it's value will result in an immediate error
   and fail to execute.
*  The ``docker_path`` option specifies the absolute path to the
   docker executable under test.  This permits both the framework
   and/or individual sub-tests to utilize a separate compiled
   executable (e.g. possibly with non-default build options).
*  The ``docker_options`` option specifies the command-line
   interface options to use **before** any sub-commands and
   their options.


``example`` Sub-test
=======================

A boiler-plate example subtest intended as a starting place for new
sub-tests.  Not all methods are required, those not overridden will
simply inherit default behavior.

``example`` Prerequisites
------------------------------

The example subtest has no prerequisites.

``example`` Configuration
-----------------------------

The example subtest configuration provides the bare_minimum
``config_version`` option.  This is required to be overridden
by all sub-tests.

``docker_cli/version`` Sub-test
=================================

Simple test that checks the output of the ``docker version`` command.

``docker_cli/version`` Prerequisites
-------------------------------------

This test requires the ``docker`` executable is available.  Optionally,
if the ``python-docker-py`` package is available, it will compare
the version number returned to the one obtained via the REST API.

``docker_cli/version`` Configuration
--------------------------------------

Two comma-separated lists of individual arguments are provided.  The
``valid_option`` list should contain arguments which will not cause
any negative results when passed to the ``docker`` command.  The
``invalid_option`` list is the opposite, every argument should cause
either a ``usage:`` statement to appear or otherwise result in a
non-zero exit code.


``docker_cli/build`` Sub-test
==============================

Tests the ``docker build`` command operation with a set of options
and pre-defined build-content.  The test subject is **not** individual
stages build process stages.  Rather, this test is only concerned
with the general behavior of the docker CLI  itself.

``docker_cli/build`` Prerequisites
------------------------------------------

*  A base or "context" directory containing a ``Dockerfile`` including
   any of it's requirements.
*  The build must complete in a fixed amount of time (i.e. no
   on external downloads, only local source content)

``docker_cli/build`` Configuration
-------------------------------------------

*  The ``docker_build_options`` option specifies additional arguments
   to add in addition to the ``DEFAULTS`` option ``docker_options``.
*  The ``docker_build_path_or_uri`` points to the absolute path
   of the base or "context" path containing the ``Dockerfile``
*  The ``build_timeout_seconds`` option specifies a fixed time (in
   seconds) the build must complete within)
*  ``try_remove_after_test`` is a boolean option, selecting whether
   or not the built-image should be removed when the test is complete.
   (Any removal errors will be ignored)
*  Both the ``repo_name_prefix`` and ``repo_name_postfix`` behave
   exactly like the `docker_cli/dockerimport sub-test`_ test.

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

* Enough disk space to construct and import several base images
  at the same time.
* The ``tar``, and ``cat`` commands.

``docker_cli/dockerimport`` Configuration
-------------------------------------------

Configuration for this subtest consists of a few options which
control overall sub-sub-test execution.  Further, unique sections
for each sub-sub-test are also used.

* The ``repo_name_prefix`` and ``repo_name_postfix`` specify
  values used to automatically generate a unique image name.
  The unique part will be sandwiched in-between these options
  values.

* ``try_remove_after_test`` is exactly like the same option in
  the `docker_cli/build sub-test`_ subtest.

* The ``test_subsubtest_postfixes`` contains a CSV listing of the
  sub-sub-test modules (and class) names to run (in order).

* The sub-sub-test section options are self-explanatory.  For this
  class of sub-test they list the tar-command location and options
  to use before sending the content into the docker import command.

----------------------------------
Dockertest and Configuration API
----------------------------------

Summary
========

All `subtest modules`_ reside beneath the ``subtest`` directory.  A subtest
module must have the same name as the directory it is in (minus the ``.py``
extension).  Other files/directories may exist at that level, but they
will not be recognized as subtest modules by the Docker client test.

Optional `configuration files`_ are located beneath the ``config.d`` directory.
They may be organized arbitrarily, however mirroring the structure of the
``subtest`` directory and subtest module names is recommended.  Configuration
options are global, however sub-tests may utilize an automatic and private
name-space.

The optional configuration name-space for sub-tests is defined as any
section's content who's name exactly matches the subtest name.  For example,
the subtest module ``subtests/docker_cli/version/version.py`` automatically
receives all options defined in the ``docker_cli/version`` section
(located in ``config.d/subtests/docker_cli/version.ini``).

Configuration Files
====================

Configuration files are located beneath the ``config.d`` directory.
They use the familiar ``ini`` style format with separate sections
containing key/value pairs.  All configuration files are loaded
into a single name-space, containing sub-name-spaces for each section.
Section names which exactly match a subtest module name, are automatically
loaded & available via the `Subtest Module`_'s ``config`` property.

Default, global values for **all** sections are located within the
special ``defaults.ini`` file's ``DEFAULTS`` section.  These option
names and values will always be available in every section, unless
overridden.

Inline-value substitution is supported using the ``%(<option>)s`` format,
where ``<option>`` is the name of another option.  The source option
name may not reside outside the reference section, though options
in the special ``DEFAULTS`` section are always available.

Dockertest API
================

Dockertest Package
------------------------

.. automodule:: dockertest
   :no-members:
   :no-undoc-members:

Version Module
----------------

.. automodule:: dockertest.version
   :members:
   :no-undoc-members:

Configuration Module
---------------------

.. automodule:: dockertest.config
   :members:
   :no-undoc-members:

Subtest Module
----------------

.. py:module:: dockertest.subtest

Adapt/extend autotest.client.test.test for Docker test sub-framework

This module provides two helper classes intended to make writing
subtests easier.  They hide some of the autotest ``test.test``
complexity, while providing some helper methods for logging
output to the controling terminal (only) and automatically
loading the specified configuration section (see `configuration module`_)

.. autoclass:: dockertest.subtest.Subtest
   :members:
   :no-inherited-members:

.. autoclass:: dockertest.subtest.SubSubtest
   :members:

Output Module
---------------

.. automodule:: dockertest.output
   :members:
   :no-undoc-members:

Xceptions Module
-------------------

.. automodule:: dockertest.xceptions
   :members:
   :undoc-members:

Sphinx Conf Module
-------------------

.. automodule:: conf
   :members:
   :undoc-members:

----------------
Further Reading
----------------

*  `Docker documentation`_
*  Autotest `results specification`_
*  `Multi-host synchronization`_ and testing

.. _`Docker documentation`: http://docs.docker.io

.. _`results specification`: https://github.com/autotest/autotest/wiki/ResultsSpecification

.. _`Multi-host synchronization`: https://github.com/autotest/autotest/wiki/Synchronizationclientsinmultihoststest

-------------------
Indices and Tables
-------------------

* :ref:`genindex`
* :ref:`modindex`

