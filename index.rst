:tocdepth: 2

.. Docker Autotest documentation master file, created by
   sphinx-quickstart on Tue Feb 18 09:56:35 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. Quick reference for reStructuredText:
   http://docutils.sourceforge.net/docs/user/rst/quickref.html

.. Reference for sphinx.ext.autodoc extension:
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
   additional

.. contents::
   :depth: 1
   :local:

----------------
Introduction
----------------

Docker Autotest_ is a sub-framework for standalone testing of docker_.
It does not depend on docker itself.  Functionally, testing occurs within
any number of subtest modules, which in some cases also include further
nested sub-subtests. It is designed to support both extremely simple,
linear, and more complex, nested, iterative testing of arbitrary external
docker commands.

Test content and configuration is fully modular, supporting both included
and external tests.  The included content is primarily focused on
continuous-integration testing of the Docker CLI client, with a very
limited amount of negative and stress testing.

As with other `Autotest Client Tests`_ the main entry point is the test
control file.  Docker Autotest's control file utilizes Autotest's
steps-engine.  This allows the overall testing state to be stored,
recovered, and resumed should a host-kernel panic or if userspace
become unresponsive.  Consequently, rebooting the host system as a
testing step is also supported.

.. _docker: http://www.docker.io

.. _Autotest: http://github.com/autotest/autotest/wiki

.. _python-docker-py: http://github.com/dotcloud/docker-py#readme

.. _Autotest Client Tests: http://github.com/autotest/autotest-client-tests

.. _docker_autotest_prereq:

----------------
Prerequisites
----------------

*  Docker

    *  **Clean** environment, only test-related images, containers
       and dependent services (besides ``docker -d``) at the start
       of **every** Autotest run.
    *  Docker installation (with ``docker -d`` running at startup)
    *  Default settings for Docker on your platform/OS,
       unless otherwise noted.
    *  Sufficient available temporary storage for multiple copies of the
       test-related images/container content.

*  `Supported Docker OS platform`_

    *  Red Hat Enterprise Linux 7 Server
    *  Fedora 20 or later recommended
    *  Linux kernel 3.12.9 or later

*  Platform Applications/tools

    *  Coreutils or equivalent (i.e. ``cat``, ``mkdir``, ``tee``, etc.)
    *  Tar and supported compression programs (``bzip2``, ``gzip``, etc.)
    *  nfs-utils (nfs-server support daemons)
    *  Git (and basic familiarity with its operation)
    *  Python 2.6 or greater (but not 3.0)
    *  Optional (for building documentation), ``make``, ``python-sphinx``,
       and ``docutils`` or equivalent for your platform.
    *  Autotest 0.16.0 or later, precise, specific version is configurable.
    *  Basic iptables based firewall, no ``firewalld`` or ``libvirtd`` running.
    *  (Optional) python-bugzilla (or equivalent) for test control based
       upon bug status.  See section `bugzilla_integration`_


*  **Any specific requirements for particular** `subtest modules`_.
   In particular:

    *  Access to a remote (to the host) image registry via ``docker pull``,
       ``http``, ``https``, and ``git``.
    *  External testing dependencies must be usable by tests w/in fixed
       timeout periods.  If an external resource or connection is too slow,
       it should be made more network-local to the test host.
    *  Most tests with external dependencies will have them flagged as
       values to the special ``__example__`` option.  See `example values`_
       for more details.

.. _Supported Docker OS platform: https://www.docker.io/gettingstarted/#h_installation

----------------
Quickstart
----------------

#.  Double-check you meet all the requirements in `docker_autotest_prereq`_.
#.  Clone autotest into ``/usr/local/autotest``

::

    [root@docker ~]# cd /usr/local
    [root@docker local]# ``git clone https://github.com/autotest/autotest.git autotest``

#.  Change to the ``client/tests`` subdirectory.
#.  Clone the `autotest-docker`_ repository into the ``docker`` subdirectory.

.. _autotest-docker: https://github.com/autotest/autotest-docker.git

::

    [root@docker local]# cd autotest/client/tests
    [root@docker tests]# git clone https://github.com/autotest/autotest-docker.git docker

#.  Change into newly checked out repository directory.
#.  Check out the most recent release by tag.
#.  Make a copy of default configuration, edit as appropriate.  Particularly
    the options for ``docker_repo_name``, ``docker_repo_tag``,
    ``docker_registry_host``, and ``docker_registry_user`` (see
    `default configuration options`_).

::

    [root@docker tests]# cd docker
    [root@docker docker]# git checkout $(git tag --list | tail -1)
    [root@docker docker]# cp -abi config_defaults/defaults.ini config_custom/
    [root@docker docker]# vi config_custom/defaults.ini

#.  Change back into the autotest client directory.

::

    [root@docker docker]# cd /usr/local/autotest/client

#.  Run the autotest standalone client (``autotest-local run docker``).  The
    default behavior is to run all subtests.  However, the example below
    demonstrates using the ``--args`` parameter to select *only two* subtests:

::

    [root@docker client]# ./autotest-local run docker --args example,docker_cli/version
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

:Note: Subtest names are all relative to the ``subtests`` subdirectory and must
       be fully-qualified.  e.g. ``docker_cli/version`` refers to the subtest module
       ``subtests/docker_cli/version/version.py``.

.. _subtests:

-----------------
Subtests
-----------------

All `subtest modules`_ reside beneath the ``subtest`` directory.  A subtest
module must have the same name as the directory it is in (minus the ``.py``
extension).  Other files/directories may exist at that level, but they
will not be recognized as subtest modules by the Docker client test.  This
ensures each subtest's code is kept separate from all others.  Finally,
every subtest is run in its own process and context.  It does not have
visibility into any other subtest code, configuration, or runtime.

Organization and Naming
=========================

The structure/layout of the ``subtest`` directory tree is relevant for
reference and configuration.  The reference and configuration section names
for subtests are formed by its relative location under the ``subtest``
directory.  For example, the subtest module ``subtests/docker_cli/version/version.py``
matches with the ``[docker_cli/version]`` configuration section and
``docker_cli/version`` subtest name.

Static Content Setup
===========================

Subtests may source their own static content from within their directory and below.
When content needs to be built, or is in some way test-environment specific, the
``setup() method`` should be overridden.  Content may be referenced from the subtest's
directory by using its ``bindir`` attribute.  A version-specific directory to
contain build/setup output is available as the ``srcdir`` attribute.  The ``setup()``
method will ***only*** be called once per version number (including revisions).
State may be reset by clearing the autotest client ``tmp`` directory.

:Note: The ``setup()`` method runs **after** the ``initialize()`` method
       only once.  If the configuration version has not changed, the method
       will not be called in subsequent Docker Autotest runs.

Sub-subtests
==============

There are provisions for tests that contain, or are composed of multiple child
tests or dependent operations.  They may share content and code between each other,
so long as it lives within the subtest directory or below.  Optionally, they may
use their own configuration sections, named by appending their class name onto
the parent subtest's name.  Sub-subtest configuration inherits undefined values
from the parent subtest configuration.  Additionally, there are multiple methods
of executing sub-subtests depending on needs.

--------------------
Images
--------------------

It is assumed that any images required for testing are available and built
beforehand.  A default image for testing purposes is required by most tests.
Its fully-qualified name is configurable, though test results will be directly
affected if it is or becomes unavailable.  Individual subtests may require
specific additional images or content.  If so, this will be noted
in the subtest documentation's *Prerequisites* section.

.. _configuration:

--------------------
Configuration
--------------------

The default configuration files are all located under the ``config_defaults``
subdirectory.  These are intended to be bundled with the autotest docker test.
To customize any subtest or global default configuration, copies should
be made manually into the ``config_custom`` subdirectory.  Any content
within ``config_custom`` will override all files and sections from
``config_defaults``.

The subdirectory structure or relative file locations under ``config_custom``
is irrelevant.  Multiple sections may appear in the same file, even for
unrelated tests.  The only exception is the ``config_custom/defaults.ini`` file
and the test ``control.ini`` file.

When customizing subtest and sub-subtest configuration options, it is highly
recommended that you add the option ``config_version`` with the current
version number, into each section.  This way, you will receive warnings when
updating Docker Autotest, if the specific custom configuration doesn't match
the API.  Generally this only happens between major/minor version updates.

Organization
==============

Sections
---------------

Configuration files use the familiar *ini* style format with separate
sections (e.g. ``[<section name>]``) preventing option names from colliding.
All configuration files are loaded into a single name-space, divided by
each section.   Section names can be arbitrary, however those which exactly
match a subtest or sub-subtest's name, will be automatically loaded (see Subtests_).

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
be folded into a single space, and combined with the previous line.

.. _example values:

Example Values
------------------

In order to help dockertest operate w/o customization, many example or demonstration
value have been configured.  While this is fine for development and informal testing
purposes, it adds external dependencies for production testing. Therefore every
option with default example values should be specified in a
comma-separated list to the special ``__example__`` option.

The ``__example__`` option's value is parsed specially.  It is not inherited from
defaults, or from subtest to sub-subtest.  Instead, it is compounded at each level
then pruned of modified options (as compared to their default/example value).  Any
unmodified options remaining at the beginning of a test will cause loud warnings
to be issued.

Value substitution
---------------------

Within each section, optional inline-value substitution is supported
using the ``%(<option>)s`` token format.  Where ``<option>`` is the
literal name of another option.  The referenced option must reside
in the same section or in the special ``DEFAULTS`` section. This is
useful when multiple option values need to be different but contain a
shared element.

Type-conversion
-----------------------

The config parser will attempt to parse each item in the following order:
integers, booleans, floats, then strings.

*  Integers are in the form of simple numbers, eg: "123"
*  Booleans are in the form 'yes' or 'true', 'no' or 'false' (case insensitive)
*  Floats are in the form of numbers with decimals eg: "123.456" or "123.0"
*  All other items will be returned as strings.

Documentation
----------------------

All configuration options must be documented somewhere at least once.
Documented options in ``[DEFAULTS]`` will automatically be documented
in subtests, no need to re-document.  Similarly, for subtests with
multiple sub-subtests, options that are overridden by sub-subtests only
need to be documented in the subtest section.

Configuration options are documented in *ReStructuredText* format
by prefixing each option with one or more comment lines that begin
with the special sequence ``#:``.  Regular line comments (beginning
with just ``#`` are not treated specially).

Documentation comments always and only apply to the next ``option = value``
sequence encountered and are otherwise ignored.  Further, all lines of
documentation are concatenated together and stripped of newlines and multiple
runs of space characters.  This is required to fit every item into a bullet
list.  Since newlines and indenting is sometimes required
(for example, a bullet list or table), special substitution sequences may
be embedded w/in the comment text:

*  Use the [unbroken] sequence ``{n}`` wherever a newline should be inserted.
*  Use the [unbroken] sequence ``{t}`` wherever a four-space indent should
   be inserted.
*  Use the sequence ``{{`` and ``}}`` to escape literal ``{`` and ``}`` characters.

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
   to predict which control file will be in use nor what its
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
       sub-subtests.  If a sub-subtest is specified without its
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
       names are ignored, and an empty list means to
       include everything from the master list.

    *  If the sub-option ``x=<thing>,<thing>,...`` appears in ``--args``,
       it will be used as the set of sub/sub-subtests to explicitly
       **exclude** from the master list above.  Unknown names are ignored,
       and an empty list means *include* everything.  Items also appearing
       in include set, will be excluded.


.. _control configuration:

Control Configuration
----------------------

To support environments where a static set of sub/sub-subtests, include
and exclude lists is needed, a completely optional control configuration
file ``control.ini`` may be used.  It uses a similar ``ini`` style configuration,
though the section names are fixed and specific.  A fully commented sample is
provided in ``config_defaults/control.ini``.  Obviously this feature is
not necessarely applicable for alternative or custom control files.

If the default control file finds a ``config_custom/control.ini`` it will be
loaded in preference to ``config_defaults/control.ini``.  The command-line ``--args``
list of sub/sub-subtests to consider will augment any also provided by
the ``subthings`` option value.  Similarly, any ``x=`` and ``i=``
sub-options to ``--args`` will augment the ``include``
and ``exclude`` option values respectively.  Command-line (``--args``) values
always take precedence over control configuration values.

After parsing all command-line and static ``control.ini`` options,
a reference copy is stored in the autotest results directory for reference.
The operational list of sub/sub-subtests (after include/exclude/bugzilla
filtering) is supplied in the ``subtests`` option value.

:**Note**:  The results directory's ``control.ini`` may optionally
            be consulted  by sub/sub-subtests.  However, its format
            and/or any contained options must always have default
            values in case of format changes or missing values.
            This facility may not be provided at all, or implemented
            differently by other control files.

.. _bugzilla_integration:

Bugzilla Integration
---------------------

This feature is only enabled if a bugzilla url option value is provided
and the ``python-bugzilla`` package is installed.  This package is available
for Fedora directly, and for Red Hat Enterprise Linux in the EPEL repository.
Most other distros similarly provide a pre-packaged version of this
python module.

When enabled in ``control.ini``, this feature helps to automatically
skip sub/sub-subtests linked to one or more outstanding bugs.  The mapping
of sub/sub-subtest to bugzilla list is specified in the ``control.ini``
file under the ``NamesToBZs`` section.  The results of querying bugzilla
are evaluated last, after the normal include/exclude lists.

.. _additional_test_trees:

Additional Test Trees
----------------------

The ``control.ini`` file may list relative directory names to be used for
test modules at different stages.  The ``subtests`` option specifies the
subdirectory that contains the main tree of tests.  Additional trees can be
named for executing test modules before, between, and after all subtest
modules.  They are named ``pretests``, ``intratests``, and ``posttests``.

:note: The include/exclude rules are simplified for additional trees.  Namely
       they are not filtered by bugzilla, and are susceptible to name collision with
       the other trees.  Care must be taken in naming modules to avoid collisions.

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

.. _subtest modules:

------------------
Subtest Modules
------------------

The following sections detail specific subtests, their configuration
and any prerequisites or setup requirements.

.. include:: subtests.rst


-------------------------
Additional Test Modules
-------------------------

The following section details included ``pretests``, ``intratests``, and ``posttests``
modules and any prerequisites or setup requirements.

.. include:: additional.rst


-------------------------------------
Dockertest |release| API Reference
-------------------------------------

Covers |release| and all revisions.

.. contents::
   :depth: 1
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

