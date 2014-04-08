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

.. sectnum::

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

*  *Any specific requirements for particular* `subtest modules`_

.. _Supported Docker OS platform: https://www.docker.io/gettingstarted/#h_installation

----------------
Quickstart
----------------

1)  Double-check you meet all the requirements in `prerequisites`_.
2)  Clone autotest into ``/usr/local/autotest``

::

    [root@docker ~]# ``git clone https://github.com/autotest/autotest.git /usr/local/autotest``

2)  Change to the ``client`` subdirectory.
3)  Create and change into the ``tests`` subdirectory (if it doesn't already exist)

::

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
6)  Check out the most recent release by tag.
7)  Make a copy of default configuration, edit as appropriate.  Particularly
    the options for ``docker_repo_name``, ``docker_repo_tag``,
    ``docker_registry_host``, and ``docker_registry_user`` (see
    `default configuration options`_).

::

    [root@docker tests]# cd docker
    [root@docker docker]# git checkout $(git tag --list | tail -1)
    [root@docker docker]# cp -abi config_defaults/defaults.ini config_custom/
    [root@docker docker]# vi config_custom/defaults.ini

8)  Change back into the autotest client directory.

::

    [root@docker docker]# cd /usr/local/autotest/client

9)  Run the autotest standalone client (``autotest-local run docker``).  The
    default behavior is to run all subtests.  However, the example below
    demonstrates using the ``--args`` parameter to select *only two* sub-tests:

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

:Note: setup() runs **after** initialize()

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
for the first two numbers (major and minor).  The third (revision)
number represents insignificant revisions which do not alter the core test
or subtest API.

This allows the API to be extended freely, but any changes
which could affect external tests or custom configurations will cause automatic
test failures when encountered.  The most likely cause for version problems is custom
and/or outdated configurations.  Double-check any customizations within
``config_custom`` match any changes to the current API.  The same goes for any private
or local tests.

Documentation versioning is similarly tied to changes in the API version.  While
non-fatal, it will introduce a delay in subtest execution.  This signal is intended
to alert developers a documentation-update pass is required to reflect changes
in the API.

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


*  For subtests which use the global default test image/repository,
   it's fully-qualified name is formed by the values to the
   ``docker_repo_name``, ``docker_repo_tag``
   ``docker_registry_host``, and ``docker_registry_user`` options.
*  The ``config_version`` option is set to the API version
   this configuration is intended for.  Because a copy of the ``defaults.ini``
   file will not inherit default version number changes, it **will** cause
   most tests to fail after changing dockertest API versions. This is
   intentional behavior and so this option must **not** be overriden
   in any subtest configuration.
*  The ``docker_path`` option specifies the absolute path to the
   docker executable under test.  This permits both the framework
   and/or individual sub-tests to utilize a separate compiled
   executable (e.g. possibly with non-default build options).
*  The ``docker_options`` option specifies the command-line
   interface options to use **before** any sub-commands and
   their options.
*  Any operations calling the docker CLI will by default,
   use the value in ``docker_timeout``.  This may be an
   integer or floating-point number specifying the number
   of seconds to allow any single command to complete.

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

The example subtest configuration is to demonstrate its values
are overridden by the ``example.ini`` under ``config_custom``.

``subexample`` Sub-test
=======================

A boiler-plate example subtest with subsubtests, intended as a
starting place for new sub-tests.  Not all methods are required,
those not overridden will simply inherit default behavior.

``subexample`` Prerequisites
------------------------------

The example subtest has no prerequisites.

``subexample`` Configuration
-----------------------------

Includes the requesite ``subsubtests`` CSV option, specifying
the subtest names to include.  Their actual execution order
us not defined.

``docker_cli/version`` Sub-test
=================================

Simple test that checks the output of the ``docker version`` command.

``docker_cli/version`` Prerequisites
-------------------------------------

Docker daemon is running and accessable by it's unix socket.

``docker_cli/version`` Configuration
--------------------------------------

None


``docker_cli/build`` Sub-test
==============================

Tests the ``docker build`` command operation with a set of options
and pre-defined build-content.

``docker_cli/build`` Prerequisites
------------------------------------------

* Tarballs bundled with the subtest
* Statically linked 'busybox' executable available over HTTP

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

``docker_cli/rm`` Sub-test
=======================================

Start up a container, run the rm subcommand on it in various ways

``docker_cli/rm`` Prerequisites
---------------------------------------------

*  None

``docker_cli/rm`` Configuration
--------------------------------------

*  Customized configuration for ``docker_repo_name``, ``docker_repo_tag``,
   and optionally ``docker_registry_host`` and/or ``docker_registry_user``.
   i.e. Copy ``config_defaults/defaults.ini`` to ``config_custom/defaults.ini``
   and modify the values.

``docker_cli/run_simple`` Sub-test
=====================================

Three simple subsubtests that verify exit status and singnal pass-through capability

``docker_cli/run_simple`` Prerequisites
-----------------------------------------

*  Container image with a ``/bin/bash`` shell executable
*  Container image with a ``/bin/true`` executable returning zero
*  Container image with a ``/bin/false`` executable returning non-zero
*  Container image with a ``/bin/date`` executable
*  Accurate (relative to host) timekeeping in container

``docker_cli/run_simple`` Configuration
-----------------------------------------

*  Customized configuration for ``docker_repo_name``, ``docker_repo_tag``,
   and optionally ``docker_registry_host`` and/or ``docker_registry_user``.
   i.e. Copy ``config_defaults/defaults.ini`` to ``config_custom/defaults.ini``
   and modify the values.


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

*  Customized configuration for ``docker_repo_name``, ``docker_repo_tag``,
   and optionally ``docker_registry_host`` and/or ``docker_registry_user``.
   i.e. Copy ``config_defaults/defaults.ini`` to ``config_custom/defaults.ini``
   and modify the values.
*  The ``remove_after_test`` option controls cleanup after all sub-subtests.
*  The ``docker_rmi_force`` option causes sub-subtests to force remove images
*  ``docker_expected_result`` should be "PASS" or "FAIL" to indicate result
   handling behavior of sub-subtests.

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

``docker_cli/stop`` Sub-test
=======================================

Several variations of running the stop command

``docker_cli/stop`` Prerequisites
---------------------------------------------

*  A remote registry server

``docker_cli/stop`` Configuration
--------------------------------------

*  Customized configuration for ``docker_repo_name``, ``docker_repo_tag``,
   and optionally ``docker_registry_host`` and/or ``docker_registry_user``.
   i.e. Copy ``config_defaults/defaults.ini`` to ``config_custom/defaults.ini``
   and modify the values.
* The ``top_name_prefix`` is prefix of the tested container followed by
* The ``run_options_csv`` modifies the running container options.
* The ``stop_options_csv`` specifies the stop command options
  random characters to make it unique.
* The ``exec_cmd`` modifies the container command
* The ``stop_duration`` sets the acceptable stop command duration (+-2s)

``docker_cli/info`` Sub-test
=================================

Simple test that checks the output of the ``docker info`` command.
It verifies the output against values obtained from userspace tools.

``docker_cli/info`` Prerequisites
-------------------------------------

*  Docker daemon is running and accessable by it's unix socket.
*  ``dmsetup`` and ``du`` commands are available.

``docker_cli/info`` Configuration
--------------------------------------

None

``docker_cli/cp`` Sub-test
=================================

Simple test that checks the success of the ``docker cp`` command.
It copies a file to a temporary directory and verifies that it was
copied successfully.

``docker_cli/cp`` Prerequisites
-------------------------------------

*  Docker daemon is running and accessable by it's unix socket.

``docker_cli/cp`` Configuration
--------------------------------------

* The ``remove_after_test`` specifies wether to remove the
  container created during the test.

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

Docker_Daemon Module
======================

.. automodule:: dockertest.docker_daemon
    :members:
    :no-undoc-members:
    :no-inherited-members:

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
*  `reStructuredText spec`_ for docstring and ``index.rst``  updates
*  Building docs, and for autodoc extension, see the `Sphinx documentation`_

.. _`Docker documentation`: http://docs.docker.io

.. _`results specification`: https://github.com/autotest/autotest/wiki/ResultsSpecification

.. _`Multi-host synchronization`: https://github.com/autotest/autotest/wiki/Synchronizationclientsinmultihoststest

.. _`reStructuredText spec`: http://docutils.sourceforge.net/rst.html

.. _`Sphinx documentation`: http://sphinx-doc.org/contents.html

-------------------
Indices and Tables
-------------------

* :ref:`genindex`
* :ref:`modindex`

