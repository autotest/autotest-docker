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
It does not strictly depend on docker itself, though it can make use
of the python-docker-py_ package (currently a reference implementation)
if/when available.  Functionally, testing occurs within a number of sub-test
modules, which in some cases also include a number of sub-sub-tests.

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

*  Docker

    *  **Clean** environment (no images or other content),
       running containers, or dependant services (besides ``docker -d``)
       at the start of **every** Autotest run.
    *  Docker installation (with ``docker -d`` running at startup)
    *  Default settings for Docker on your platform/OS,
       unless otherwise noted.
    *  (Optional) The python-docker-py_ package for your platform

*  `Supported Docker OS platform`_

    *  Fedora 20 recommended
    *  Linux kernel 3.12.9 or later

*  Platform Applications/tools

    *  Core-utils or equivalent (i.e. ``cat``, ``mkdir``, ``tee``, etc.)
    *  Tar and supported compression programs
    *  Git (and basic familiarity with it's operation)
    *  Python 2.4 or greater (but not 3.0)
    *  Optional (for building documentation), ``make`` and ``python-sphinx``
       or the equivilent for your platform (supplying the ``sphinx-build``
       executable)

*  Autotest & Autotest Client (0.15 or later)

    *  Git clone of https://github.com/autotest/autotest.git

                        *or*

    *  Platform-specific binary package (e.g. ``autotest-framework``)

    *  Environment variable ``AUTOTEST_PATH`` set to absolute path where
       autotest installed (if *not* in ``/usr/local/autotest``)

*  *Any specific requirements for particular* `subtest modules`_

.. _Supported Docker OS platform: https://www.docker.io/gettingstarted/#h_installation

----------------
Quickstart
----------------

1)  Double-check you meet all the requirements in `prerequisites`_.
2)  Within your ``$AUTOTEST_PATH``, change to the ``client`` subdirectory.
3)  Create and change into the ``tests`` subdirectory (if it doesn't already exist)

::

    [root@docker ~]# cd $AUTOTEST_PATH
    [root@docker autotest]# cd client
    [root@docker client]# mkdir tests
    [root@docker client]# cd tests
    [root@docker tests]#

4)  Clone the `autotest-docker`_ repository into the ``docker`` subdirectory.

::

    [root@docker tests]# git clone https://github.com/autotest/autotest-docker.git docker
    Cloning into 'docker'...
    remote: Reusing existing pack: ... done.
    remote: Counting objects: ..., done.
    remote: Compressing objects: ..., done.
    remote: Total .., reused ...
    Receiving objects: ..., done.
    Resolving deltas: ..., done.
    Checking connectivity... done.

.. _autotest-docker: https://github.com/autotest/autotest-docker.git

5)  Change into newly checked out repository directory.
6)  Make a copy of default configuration, edit as appropriate.  Particularly
    the options for ``docker_repo_name``, ``docker_repo_tag``,
    ``docker_registry_host``, and ``docker_registry_user`` if required.

::

    [root@docker tests]# cd docker
    [root@docker docker]# cp -abi config_defaults/defaults.ini config_custom/
    [root@docker docker]# vi config_custom/defaults.ini

7)  Change back into the autotest client directory.
8)  Run the autotest standalone client (``autotest-local run docker``).  The
    default behavior is to run all subtests.  However, the example below
    demonstrates using the ``--args`` parameter to select *only two* sub-tests:

::

    [root@docker docker]# cd ../../
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

:Note: Subtest names are all relative to the ``subtests`` sub-directory and must
       be fully-qualified.  e.g. ``docker_cli/version`` refers to the subtest module
       ``subtests/docker_cli/version/version.py``.

-----------------
Subtests
-----------------

All `subtest modules`_ reside beneath the ``subtest`` directory.  A subtest
module must have the same name as the directory it is in (minus the ``.py``
extension).  Other files/directories may exist at that level, but they
will not be recognized as subtest modules by the Docker client test.  This
ensures each subtest's code is kept separate from all others.

The structure/layout of the ``subtest`` directory tree is not important
for locating/executing subtests.  However it is relevant for the finding/loading
of each subtests configuration_.  The configuration **section name** for any sub-tests
is formed by the subtest name relative to the ``subtest`` directory.  For example,
the subtest module ``subtests/docker_cli/version/version.py`` matches with
the ``[docker_cli/version]`` *configuration section*.  The relative location
of the configuration file does not matter, only the section name.

Additionally, subtests may source their own static content.  If this content
is further test components, please see the `Subtest Module`_ section regarding the
``dockertest.subtest.SubSubtest`` class.  If static content needs to be built,
or in some  way made environment-specific, this must happen by overriding
the ``setup() method``.  Within this method, content it should be copied from
from the path referenced in the ``bindir`` attribute, to the path referenced
by the ``srcdir`` attribute.  The ``setup()`` method will ***only*** be called
once per version number (including revisions).  State may be reset by clearing
the autotest client ``tmp`` directory.

--------------------
Images
--------------------

Multiple areas of documentation and output refer to *repository*, *images*,
and *layers* almost interchangeably.  There are also multiple interfaces
available for image creation, retrieval, comparison, etc. these items.  However,
images are extremely central to working with containers in general, and
with docker specifically.  A generalized interface for working with these
items is provided by the `images module`_.

This module wraps many concepts up inside constructs to provide a measured
amount of abstraction.  It allows subtests and other callers to expand
it's concepts while providing a high-level consistent, extensible and
uniform set of helpers.  Most of them are designed to be agnostic toward
the actual method of image access or representation.

Though for internal use it is highly recommended to reference images only
by their long (64-character) ID string.  Otherwise, for specific test-subjects,
or use,  any of the provided interfaces may be used and/or specialized.  Extension
of interfaces can be done within subtest modules directly, or some combination
of sources.

--------------------
Configuration
--------------------

The default configuration files are all located under the ``config_defaults``
sub-directory.  These are intended to be bundled with the autotest docker test.
To customize any subtest or global default configuration, copies should
be made manually into the ``config_custom`` sub-directory.  Any content
within ``config_custom`` will override anything found under
``config_defaults``.  Nothing except for the example ``config_custom/example.ini``
should be checked into version control.

Configuration files use the familiar ``ini`` style format with separate
sections (e.g. ``[<section name>]``) preventing option names from colliding.
All configuration files are loaded into a single name-space, containing
sub-name-spaces for each section. Section names which exactly match a subtest
module name, are automatically loaded (see Subtests_).

The Default, global values for **all** sections are located within the
special ``defaults.ini`` file's ``DEFAULTS`` section.  These option
names and values stand in for same-named options that are undefined
in any section. See `Default configuration options`_ for more details.

Optional inline-value substitution is supported using the ``%(<option>)s`` format,
where ``<option>`` is the name of another option.  The source option
name may not reside outside the reference section, though options
in the special ``DEFAULTS`` section are always available.

:Note: The relative locations of files under ``config_defaults`` and ``config_custom``
       does not matter.  Multiple sections may appear in the same file.

------------------------
Versioning Requirements
------------------------

In order to support external/private subtests and customized configurations,
the Docker Autotest API version has been tightly coupled to test content,
configuration, and documentation.  Version comparison is only significant
for the first two numbers (the major and minor versions).  The third (last)
number represents insignificant revisions which do not alter the core test
or subtest API.

This allows the API to be extended freely, but any changes
which could affect external tests or custom configurations will be flagged
when encountered.  The most likely cause for version problems is custom
and/or outdated configurations.  Double-check any customizations within
``config_custom`` match the current API.

------------------
Subtest Modules
------------------

The following sections detail specific sub-tests, their configuration
and any prerequisites or setup requirements.

Default configuration options
================================

Global default options that apply to all other sections are set in
the special ``DEFAULTS`` section of the ``defaults.ini`` file.  This
file is loaded *either* from ``config_defaults`` *or* ``config_custom``.

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
if the ``python-docker-py`` package is available, it will be used.  If
it fails, a simple check using the REST API is used to compare
the version number returned to the one obtained from the CLI. This check
requires the 'nc' (netcat) command is available.

``docker_cli/version`` Configuration
--------------------------------------

Only the API version.


``docker_cli/build`` Sub-test
==============================

Tests the ``docker build`` command operation with a set of options
and pre-defined build-content.

``docker_cli/build`` Prerequisites
------------------------------------------

* Tarballs bundled with the subtest
* Statically linked 'busybox' executable available on PATH
  in host environment.

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
   is specified by the ``busybox_path`` option.

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

* The ``image_name_prefix`` and ``image_name_postfix`` specify
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


``docker_cli/images`` Sub-test
=======================================

Ultra-simple test to confirm output table-format of docker CLI
'images' command.

``docker_cli/images`` Prerequisites
---------------------------------------------
*  None

``docker_cli/images`` Configuration
--------------------------------------
*  None


``docker_cli/run_simple`` Sub-test
=====================================

Three simple tests that verify exit status and singnal pass-through capability

``docker_cli/run_simple`` Prerequisites
-----------------------------------------

*  Container image with a ``/bin/bash`` shell executable
*  Container image with a ``/bin/true`` executable returning zero
*  Container image with a ``/bin/false`` executable returning non-zero

``docker_cli/run_simple`` Configuration
-----------------------------------------

*  Customized configuration for ``docker_repo_name``, ``docker_repo_tag``,
   and optionally ``docker_registry_host`` and/or ``docker_registry_user``.
   i.e. Copy ``config_defaults/defaults.ini`` to ``config_custom/defaults.ini``
   and modify the values.


``docker_cli/pull`` Sub-test
=======================================

Several variations of running the pull command against a registry server.

``docker_cli/pull`` Prerequisites
---------------------------------------------

*  A remote registry server
*  Image on remote registry with 'latest' and some other tag

``docker_cli/pull`` Configuration
--------------------------------------

*  Customized configuration for ``docker_repo_name``, ``docker_repo_tag``,
   and optionally ``docker_registry_host`` and/or ``docker_registry_user``.
   i.e. Copy ``config_defaults/defaults.ini`` to ``config_custom/defaults.ini``
   and modify the values.

``docker_cli/commit`` Sub-test
=======================================

Several variations of running the commit command

``docker_cli/commit`` Prerequisites
---------------------------------------------

*  A remote registry server
*  Image on remote registry with 'latest' and some other tag

``docker_cli/commit`` Configuration
--------------------------------------

*  Customized configuration for ``docker_repo_name``, ``docker_repo_tag``,
   and optionally ``docker_registry_host`` and/or ``docker_registry_user``.
   i.e. Copy ``config_defaults/defaults.ini`` to ``config_custom/defaults.ini``
   and modify the values.

----------------------------------
Dockertest API Reference
----------------------------------

Dockertest Package
========================

.. automodule:: dockertest
   :no-members:
   :no-undoc-members:

Subtest Module
================

.. Have to list out contents one-by-one for this module
   otherwise the Mock'd inherited test.test prevents
   Subtest class from containing any detail

.. py:module:: dockertest.subtest

Adapt/extend autotest.client.test.test for Docker test sub-framework

This module provides two helper classes intended to make writing
subtests easier.  They hide some of the autotest ``test.test``
complexity, while providing some helper methods for logging
output to the controlling terminal (only) and automatically
loading the specified configuration section (see `configuration module`_)

.. autoclass:: dockertest.subtest.Subtest
   :members:
   :no-inherited-members:

.. autoclass:: dockertest.subtest.SubSubtest
   :members:

.. autoclass:: dockertest.subtest.SubSubtestCaller
   :members:

Images Module
===============

.. automodule:: dockertest.images
   :members:
   :no-undoc-members:

Containers Module
==================

.. automodule:: dockertest.containers
   :members:
   :no-undoc-members:

Networking Module
==================

.. automodule:: dockertest.networking
   :members:
   :no-undoc-members:

Dockercmd Module
=================

.. automodule:: dockertest.dockercmd
   :members:
   :no-undoc-members:

Output Module
===============

.. automodule:: dockertest.output
   :members:
   :no-undoc-members:

Xceptions Module
===================

.. automodule:: dockertest.xceptions
   :members:
   :undoc-members:

Sphinx Conf Module
===================

.. automodule:: conf
   :members:
   :undoc-members:

Version Module
================

.. automodule:: dockertest.version
   :members:
   :no-undoc-members:

Configuration Module
=====================

.. automodule:: dockertest.config
   :members:
   :no-undoc-members:

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

