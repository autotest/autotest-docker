:tocdepth: 2

.. Docker Autotest documentation master file, created by
   sphinx-quickstart on Tue Feb 18 09:56:35 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. Quick reference for reStructuredText:
   http://docutils.sourceforge.net/docs/user/rst/quickref.html

.. Reference for sphinx.ext.autodoc extenstion:
   http://sphinx-doc.org/ext/autodoc.html


=====================================
Docker Autotest |version|
=====================================

.. sectnum::

.. toctree::
   :hidden:
   :numbered:

   defaults
   subtests

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

.. _docker_autotest_prereq:

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
    *  Python 2.6 or greater (but not 3.0)
    *  Optional (for building documentation), ``make`` and ``python-sphinx``
       or the equivalent for your platform (supplying the ``sphinx-build``
       executable)
    *  Autotest 0.15.0 or later, specific version is configured.

*  *Any specific requirements for particular* `subtest modules`_

.. _Supported Docker OS platform: https://www.docker.io/gettingstarted/#h_installation

----------------
Quickstart
----------------

1)  Double-check you meet all the requirements in `docker_autotest_prereq`_.
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
ensures each subtest's code is kept separate from all others.  Finally,
every subtest is run in it's own process and context.  It does not have
visibility into any other subtest code, configuration, or runtime.

Organization and Naming
=========================

The structure/layout of the ``subtest`` directory tree is relevant for
reference and configuration.  The reference and configuration section names
for subtests are formed by it's relative location under the ``subtest``
directory.  For example, the subtest module ``subtests/docker_cli/version/version.py``
matches with the ``[docker_cli/version]`` configuration section and
``docker_cli/version`` subtest name.

Static Content Setup
===========================

Subtests may source their own static content from within their directory and below.
When content needs to be built, or is in some way test-environment specific, the
``setup() method`` should be overridden.  Content may be referenced from the subtest's
directpory by using it's ``bindir`` attribute.  A version-specific directory to
contain build/setup output is available as the ``srcdir`` attribute.  The ``setup()``
method will ***only*** be called once per version number (including revisions).
State may be reset by clearing the autotest client ``tmp`` directory.

:Note: The ``setup()`` method runs **after** the ``initialize()`` method
       only once.  If the configuration version has not changed, the method
       will not be called in subsequent Docker Autotest runs.

Sub-subtests
==============

There are provisions for tests that contain, or are composed of multiple child
tests or dependant operations.  They may share content and code between eachother,
so long as it lives within the subtest directory or below.  Optionally, they may
use their own configuration sections, named by appending their class name onto
the parent subtest's name.  Sub-subtest configuration inherits undefined values
from the parent subtest configuraion.  Additionally, there are multiple methods
of executing sub-subtests depending on needs.  Please see the `Subtest Module`_
API reference regarding the ``dockertest.subtest.SubSubtest`` class and "caller"
methods.

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

Organization
==============

Sections
---------------

Configuration files use the familiar *ini* style format with separate
sections (e.g. ``[<section name>]``) preventing option names from colliding.
All configuration files are loaded into a single name-space, divided by
each section.   Section names can be arbitrary, however those which exactly
match a subtest or subsubtest's name, will be automatically loaded (see Subtests_).

.. _default configuration options:

Defaults
----------------

The Default, global values for **all** sections are located within the
special ``defaults.ini`` file's ``DEFAULTS`` section.  These option
names and values are supplied for all sections which do not contain
a identical named option.  This file is loaded *either* from the
``config_defaults`` *or* ``config_custom`` directory.


.. include:: defaults.rst


Formatting
=============

Long values
----------------

Long values may be continued onto the next line by prefixing any run of one or
more horizontal-whitespace characters with a newline.  For example:

     option_name = This option value is super duper long,
                   but will be un-folded into a single string with
                   <---- all this whitespace replaced by a single space.

In this case, the runs of multiple whitespace following the newline will
be folded into a single instance, and substituted for the previous newline.

Value substitution
---------------------

Within each section, optional inline-value substitution is supported
using the ``%(<option>)s`` token format.  Where ``<option>`` is the
literal name of another option.  The referenced option must reside
in the same section or in the special ``DEFAULTS`` section. This is
useful when multiple option values need to be different but contain a
shared element.

:Note: The relative locations of files under ``config_defaults`` and ``config_custom``
       does not matter.  Multiple sections may appear in the same file.

Type-conversion
-----------------------
The config parser will attempt to parse each item in the following order:
integers, booleans, floats, then strings.

*  Integers are in the form of simple numbers, eg: "123"
*  Booleans are in the form 'yes' or 'true', 'no' or 'false' (case insensitive)
*  Floats are in the form of numbers with decimals eg: "123.456" or "123.0"
*  All other items will be returned as strings.


------------------------
Autotest Integration
------------------------

Control files
===============

Every test in autotest makes use of a ``control`` file as the single
operational bridge between the Autotest server/client and the underlying
testing details.  This arrangement allows tests to ignore higher-level
details, like intra-test reboots, reporting, iteration.  Instead, tests
can remain focused on exercising their subjects with a loose set of
input variables an provided initial environment.  More details about
control files and their standards can be found in the Autotest documentation.

Jobs interface
================

This is the highest level of abstraction exposed to control files.
The ``job`` object is implicitly passed into the control file, and used
to produce test objects.  Docker autotest makes use of several standard
facilities provided by the job object:

*  The ``job.resultdir`` attribute points to the top-level absolute
   directory where all results and logs will be recorded.  This
   directory contains a copy of the control file used, as well as
   logs and results for every test object executed.

*  The ``job.control`` attribute points to the absolute path
   of the control file currently in use.  Though primarily for
   reference purposes, any use of this by lower-level tests
   can only be on an advisory basis.  There is no way for tests
   to predict which control file will be in use nor what it's
   precise behavior will be.

*  The ``job.args`` attribute contains a list of space-separated
   arguments passed to the control file.  This can be via the
   ``--args`` option to the Autotest client, or it can come from
   elsewhere.  Other than parsing the value into the list,
   it's entirely up to the control file and/or tests to do what
   they need with this facility.

*  The ``job.next_step()`` method is used by the control file
   to set up and establish the harness-state for each distinct
   operation.  While the state can be arbitrary, Docker Autotest
   uses this facility to insert test objects for eventual execution.
   Each step will ultimately be executed in a forked process,
   so there is no chance they may directly or accidentally
   influence each other's python-environment.

Test interface
================

Autotest test objects are the primary context which contain
testing-behavior and implementation details.  In Docker
autotest, each Subtest is derived from the autotest test.test
class.  With some help from the control file, this allows
otherwise separate tests to be bundled together and executed
in sequence, while sharing some common code.  The important
details/components of the test interface are available
in the `Subtest Module`_ section.


Docker Autotest Control
=========================

The example control file provided with Docker autotest is designed
to locate and setup particular subtests for execution via the
``job.next_step()`` mechanism.  Once the steps are initialized,
execution passes back into the Autotest client harness.

To help with the complex task of specifying which subtests (and
sub-subtests) are available for running, the control file makes
use of the ``jobs.args`` attribute value in the following way:

    *  The value is treated as a order-sensitive space-separated
       list of values.  Any subtests or sub-subtest names listed
       alone (space separated) or with commas and no intervening spaces,
       will be added to the master list of sub/sub-subtests to
       consider for testing.  The sequence (including duplicates)
       is important, and preserved.

    *  It's possible to specify both subtest and sub-subtest names,
       to the ``--args`` option.  However, only job steps will be
       added for subtests since Autotest has no knowledge of
       sub-subtests.  If a sub-subtest is specified without it's
       parent subtest, the control file will automatically inject
       the parent subtest into the master list, ahead of the sub-subtest
       if it's not already listed.

    *  If no subtests or sub-subtests are specified via ``jobs.args``,
       the master list will be automatically generated by
       searching for all applicable modules containing a
       ``test.test`` class or subclass.  The order they will be
       added is undefined.

    *  If a ``jobs.args`` sub-option in the form ``i=<thing>,<thing>,...``
       appears, it will be considered as the set of sub/sub-subtest names
       to explicitly **include** from the master list (above).  Unknown
       any unknown names are ignored, and an empty list means to
       include everything from the master list.

    *  If the sub-option ``x=<thing>,<thing>,...`` appears in ``--args``,
       it will be used as the set of sub/sub-subtests to explicitly
       **exclude** from the master list above.  Unknown names are ignored,
       and an empty list means *include* everything.  Items also appearing
       in include set, will be excluded.

Control Configuration
----------------------

To support environments where a static set of sub/sub-subtests, include
and exclude lists is needed, a completely optional control configuration
file may be used.  It's format is identical to what is used for Docker
Autotest `Configuration`_.  A fully commented sample is provided in
``config_defaults/control.ini``.

If the control file finds a ``config_custom/control.ini`` it will be
loaded in preference to ``config_defaults/control.ini``.  The ``jobs.args``
list of sub/sub-subtests to consider will augment any also provided by
the ``subthings`` option value.  Similarly, The ``x=`` and ``i=``
sub-options in ``jobs.args`` (if found) will augment the ``include``
and ``exclude`` option values.  Command-line (``jobs.args``) values
always take precedence over control configuration values.

After parsing all command-line and static ``control.ini`` options,
a reference copy is stored in ``job.resultdir`` by the control file.
The operational list of sub/sub-subtests (after include/exclude/bugzilla
filtering) is supplied in the ``subtests`` option value.

:**Note**:  The results directory's ``control.ini`` may optionally
            be consulted  by sub/sub-subtests.  However, it's format
            and/or any contained options must always have default
            values in case of format changes or missing values.
            This facility may not be provided at all, or implemented
            differently by other control files.

Bugzilla Integration
---------------------

This feature is only enabled if a bugzilla url option value is provided
and the ``python-bugzilla`` package is installed.  This package is available
for Fedora directly, and for Red Hat Enterprise Linux in the EPEL repository.
Most other distros. Similarly provide a pre-packaged version of this
python module.

When enabled in ``control.ini``, this feature helps to automatically
skip sub/sub-subtests linked to one or more outstanding bugs.  The mapping
of sub/sub-subtest to bugzilla list is specified in the ``control.ini``
file under the ``NamesToBZs`` section.  The results of querying bugzilla
are evaluated last, after the normal include/exclude lists.

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

.. contents::
   :depth: 1
   :local:

-------------------------------------
Dockertest |release| API Reference
-------------------------------------

Covers |release| and all revisions.

.. contents::
   :depth: 4
   :local:

Dockertest Package
========================

.. automodule:: dockertest
   :no-members:
   :no-undoc-members:

Subtest Module
================

.. automodule:: dockertest.subtest
   :members:
   :no-undoc-members:

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


Environment Module
===================

.. automodule:: dockertest.environment
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

Documentation Module
====================

.. automodule:: dockertest.documentation
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

*  :ref:`genindex`
*  :ref:`modindex`

