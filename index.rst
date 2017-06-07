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
    *  Docker installation (with docker daemon running)
    *  Default settings for Docker on your platform/OS,
       including storage (LVM thin-pool + XFS).
    *  Sufficient available temporary storage for multiple copies of the
       test-related images/container content.

*  `Supported Docker OS platform`_

    *  Red Hat Enterprise Linux 7 Server (preferred for development)
    *  Red Hat Enterprise Linux Atomic Host (preferred for testing)
    *  Fedora 22 or later including Atomic (not all tests may function)
    *  Other platforms (such as CentOs, SLES, Ubuntu) un-maintained but possible.

*  Platform Applications/tools

    *  Autotest 0.16.0 or later.
    *  Coreutils or equivalent (i.e. ``cat``, ``mkdir``, ``tee``, etc.)
    *  Tar and supported compression programs (``bzip2``, ``gzip``, etc.)
    *  nfs-utils (nfs-server support daemons)
    *  Python 2.6 or greater (not 3.0)
    *  libselinux-python 2.2 or later
    *  Optional (for building documentation), ``make``, ``python-sphinx``,
       and ``docutils`` or equivalent for your platform.
    *  Optional (for running unittests), ``pylint``, ``pep8``,
       ``python-unittest2``, and ``python2-mock``.
    *  Optional, ``python-bugzilla`` for test exclusion based
       upon bug status.  See ``control.ini`` file comments for details.


*  **Any specific requirements for particular** `subtest modules`_.
   In particular:

    *  Direct root access for running docker, restarting the daemon,
       and accessing metadata / storage details.  Running through
       sudo may work to a degree, but is likely to cause problems.
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

All platforms
=============

#.  Double-check you meet all the requirements in `docker_autotest_prereq`_.  For
    the quickstart, either a RHEL 7 or Fedora 25 system is assumed with the Docker
    daemon started, device-mapper or overlay2 storage configured, and at
    least 10gig of registry space is available.

#.  As ``root``, shallow-clone Autotest (**non-recursive**) into ``/var/lib/autotest``,
    and set/export the ``AUTOTEST_PATH`` environment variable to it's location.

    ::

        [root@docker ~]# cd /var/lib

        [root@docker lib]# git clone --single-branch --depth 1 \
        https://github.com/autotest/autotest.git autotest

        [root@docker lib]# export AUTOTEST_PATH=/var/lib/autotest

#.  Change to the autotest client subdirectory.

#.  Clone `autotest-docker`_ repository into the ``docker`` subdirectory.
    Based from a `formal release`_ or the latest available.

    ::

        [root@docker lib]# cd $AUTOTEST_PATH/client

        [root@docker client]# git clone --branch $VERSION \
        https://github.com/autotest/autotest-docker.git tests/docker

    Where ``$VERSION`` is the docker-autotest release (e.g. "|version|")
    **or** to use the current latest release, omit the --branch option:

    ::

        [root@docker client]# git clone \
        https://github.com/autotest/autotest-docker.git docker


#.  Make a copy of default configuration, then edit as appropriate.
    Particularly, verify the CSV list of full-image names and
    container names, ``preserve_fqins`` and ``preserve_cnames``
    are set correctly.  **All other images/containers will be destroyed!**
    See `default configuration options`_ for more details.

    ::

        [root@docker client]# cp -abi tests/docker/config_defaults/defaults.ini \
        tests/docker/config_custom/

        [root@docker client]# $EDITOR tests/docker/config_custom/defaults.ini

.. _autotest-docker: https://github.com/autotest/autotest-docker.git
.. _`formal release`: https://github.com/autotest/autotest-docker/releases

Fedora platforms
=================

The Fedora base-images lack some essential tooling necessary for testing.  In addition
to the steps above, a custom test-image must be configured for building.

#.  Edit the ``defaults.ini`` file again, and change the registry settings as follows:

    ::

        [root@docker client]# $EDITOR tests/docker/config_custom/defaults.ini

        ...
        docker_registry_host = localhost
        docker_registry_user =
        docker_repo_name = fedora_test_image
        docker_repo_tag = latest
        ...

#.  Make a copy of the ``docker_test_images.ini`` configuration file and configure
    it to build the test image.

    ::

        [root@docker client]# cp -abi tests/docker/config_defaults/docker_test_images.ini \
        tests/docker/config_custom/

        [root@docker client]# $EDITOR tests/docker/config_custom/docker_test_images.ini

        ...
        build_name = localhost/fedora_test_image:latest
        build_dockerfile = https://github.com/autotest/autotest-docker/raw/master/fedora_test_image.tar.gz
        build_opts_csv = --no-cache,--pull,--force-rm
        ...

Execute and examine results
============================

For all platforms, use the standalone autotest client to select and execute subtests.
The default behavior is to run all subtests.  However, the example below only
executes the ``version`` subtest for demonstration purposes.  This will bring in
some additional utility "tests", such as ``docker_test_images`` and ``garbage_check``.
Other subtests may be selected via the ``--args`` `parameter or by customizing`_
``control.ini``.

::

    [root@docker /]# cd $AUTOTEST_PATH/client

    [root@docker client]# ./autotest-local tests/docker/control --args=docker_cli/version
    Writing results to /var/lib/autotest/client/results/default
    START	----	----
    Subtest/Sub-subtest requested:
            'docker_cli/version'

    Subtest/sub-subtest exclude list:
            'subexample'
            'pretest_example'
            'example'
            'intratest_example'
            'posttest_example'

    Executing tests:
            'docker/pretests/docker_test_images.1'
            'docker/pretests/log_sysconfig.2'
            'docker/pretests/log_versions.3'
            'docker/subtests/docker_cli/version.4'
            'docker/intratests/garbage_check.4'

        START	docker/pretests/docker_test_images.1
        docker_test_images: initialize()
        docker_test_images: setup() for subtest version 2055
        docker_test_images: Running sub-subtests...
            puller: initialize()
            puller: run_once()
            puller: Pulling registry.access.redhat.com/rhel7/rhel:latest
            puller: Pulling docker.io/stackbrew/centos:latest
            puller: postprocess()
            puller: cleanup()
            builder: initialize()
            builder: run_once()
            builder: postprocess()
            builder: cleanup()
        docker_test_images: postprocess_iteration() #0 of #1
        docker_test_images: full_name:registry.access.redhat.com/rhel7/rhel:latest
        docker_test_images: full_name:docker.io/stackbrew/centos:latest
        docker_test_images: Updated preserve_fqins: docker.io/stackbrew/centos:latest,registry.access.redhat.com/rhel7/rhel:latest
        docker_test_images: Postprocess sub-subtest results...
        docker_test_images: cleanup()
            GOOD	docker/pretests/docker_test_images.1
        END GOOD	docker/pretests/docker_test_images.1
        START	docker/pretests/log_sysconfig.2
        log_sysconfig: initialize()
        log_sysconfig: setup() for subtest version 0
        log_sysconfig: run_once()
        log_sysconfig: postprocess_iteration() #0 of #1
        log_sysconfig: postprocess()
        log_sysconfig: cleanup()
            GOOD	docker/pretests/log_sysconfig.2
        END GOOD	docker/pretests/log_sysconfig.2
        START	docker/pretests/log_versions.3
        log_versions: initialize()
        log_versions: setup() for subtest version 0
        log_versions: run_once()
        log_versions: Found docker version client: 1.12.6 server 1.12.6
        log_versions: postprocess_iteration() #0 of #1
        log_versions: postprocess()
        log_versions: cleanup()
            GOOD	docker/pretests/log_versions.3
        END GOOD	docker/pretests/log_versions.3
        START	docker/subtests/docker_cli/version.4
        version: initialize()
        version: setup() for subtest version 0
        version: run_once()
        version: postprocess_iteration() #0 of #1
        version: postprocess()
        version: docker version client: 1.12.6 server 1.12.6
        version: Docker cli version matches docker client API version
        version: cleanup()
            GOOD	docker/subtests/docker_cli/version.4
        END GOOD	docker/subtests/docker_cli/version.4
        START	docker/intratests/garbage_check.4
            GOOD	docker/intratests/garbage_check.4
        END GOOD	docker/intratests/garbage_check.4
    END GOOD	----	----


*(timestamps and extra inconsequential text removed for clarity)*

Examine the test results by changing to the ``results/default`` directory.
*Note:* The name "default" is used when no ``--tag`` option is given to the
``autotest-local`` command.

::

    [root@docker client]# cd $AUTOTEST_PATH/client/results/default

    [root@docker default]# ls -1
    control          # Copy of the control file used for the run
    control.ini      # Runtime configuration from default control file
    control.state    # Used to support mid-test reboot / test resumption
    debug            # All the client / sydout/stderr recorded by log-level.
    docker           # Directory-tree of subtest results by name
    job_report.html  # Autogenerated report web-page.
    status           # Text-version of test run / results
    status.json      # Same thing, but in JSON format.
    sysinfo          # Directory of important log-files for the run.

    [root@docker default]# ls -1 docker/subtests/docker_cli/version.4/
    debug            # Same as above, but ONLY logs for this subtest
    keyval           # Copy of subtest configuration, including defaults
    profiling        # Not used
    results          # Not used
    status           # Same as above, but ONLY for this subtest
    sysinfo          # Logs captured after this subtest ran.

If you wish jUnit format results, execute the included conversion script.

::

    [root@docker client]# cd $AUTOTEST_PATH/client
    [root@docker client]# tests/docker/results2junit --name $HOSTNAME results/default

    [root@docker client]# cat results/default/results.junit
    <testsuites>
        <testsuite name="localhost" failures="0" tests="5" skipped="0" errors="0">
            <testcase classname="localhost.pretests" name="docker_test_images" time="29"/>
            ...

.. _`parameter or by customizing`: _selecting subthings


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

The example ``control`` file provided with Docker autotest is
designed to locate and setup subtests for execution in a particular
way.  However, this is only an example, you may customize or provide
your own ``control`` file if alternate behavior is desired.

.. _selecting subthings:

Selecting Sub-test and Sub-subtest modules
------------------------------------------

To help with the complex task of locating and queuing subtests
for execution.  The default ``control`` file examines two possibly
complementary sets of options.  One is via the ``--args`` autotest client
command-line option.  The other is via the ``control.ini`` file.  This
file is typically copied from ``config_defaults`` and modified in
``config_custom``.

.. _args configuration:

**``--args`` Reference:**

    *  The value is treated as a sequence of space-separated then
       comma-separated list of values.  Any subtests or sub-subtest
       names listed alone (space separated), or with commas and no
       intervening spaces, will be added to list of candidates.

    *  If no candidate subtest or sub-subtest list are specified,
       the list will be generated by searching for applicable
       modules under ``subtests``, ``pretests``, ``intratests`` and
       ``posttests``.

    *  If a space-separated component of ``--args`` is of the
       form ``i=<name>,<name>,...``.  Then each ``<name>`` will
       be taken from the candidate list, as a test module to include
       in the run-queue.  Unknown names are ignored with a warning.

    *  Similarly, a space-separated component of the form
       ``x=<thing>,<thing>,...`` is taken as the list of test modules
       to exclude from the run-queue.  Any conflicts with the include
       list, will result in the item being excluded.

    *  If the string ``!!!`` appears as any of the space-separated
       items to ``--args``, then **no** tests will be executed.
       Instead, the run-queue will simply be displayed and logged.

.. _control configuration:

**``control.ini`` Reference:**

    * A ``config_custom/control.ini`` will be loaded in preference
      to ``config_defaults/control.ini``.

    * The ``subthings`` option takes a CSV list of candidate module
      names, similar to the space-separated sequence from ``--args``
      (above).

    * The ``pretests``, ``intratests`` and ``posttests`` items specify
      the relative path to directories to search for candidates if
      they're not specified in the ``subthings`` list (or in ``--args``).

    * The ``include`` and ``exclude`` CSV lists operate just as expected.
      Either including or excluding items from the candidate list, into
      the run-queue.

    * All the other options are fully documented within the
      ``config_custom/control.ini`` file.

:**Note**:  The ``$AUTOTEST_PATH/client/results/default/control.ini``
            represents the parsed, run-time copy of the file.  It is
            consumed and used internally by Docker Autotest and should
            be considered read-only.

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
Hacking
----------------


Rolling a new minor version
===========================

When the time is right, a large number of PRs have been merged, and you're in
the right mood, it's time for a new minor release.  Assuming the last tagged
version was ``0.8.6``, here are the steps required:

#. Make sure your master branch exactly matches upstream:

    ``git remote update``
    ``git checkout master``
    ``git reset --hard upstream/master``

#. Create a new branch off master with the next number:

    ``git checkout -tb 0.8.7``

#. Bump the version number up in three places:

    ``$EDITOR config_defaults/defaults.ini dockertest/version.py conf.py``

#. Create a release commit:

    ``git commit -asm "Dockertest Version 0.8.7 (NO API Changes)"``

#. Push to your fork, and open a PR targeting the previous milestone, ``0.8.7``
   in this case.

#. After PR is merged, switch back to master, update it, and tag the version, and push.

    ``git remote update``
    ``git checkout master``
    ``git reset --hard upstream/master``
    ``git tag 0.8.7 HEAD``
    ``git push --tags upstream``

#. `Create a new release`_, using the just tagged version and the closed milestone
   as the title.  e.g. "``Dockertest Version 0.8.7 (NO API Changes)``".  This will
   cause github to automatically produce a zip and tarball, with URLs for historical
   reference or use (i.e. somewhere ``git`` is not available).

   For the release notes (big text box under the title), link to the github
   comparison URL formed by the last two tags with ``...`` in-between (end of the url):

    ``[Changes](https://github.com/autotest/autotest-docker/compare/0.8.6...0.8.7)``

   The actual github comparison page (URL above) can also be used as reference for
   drafting a release-announcement e-mail, providing brownie-points and karma
   for all the people who helped out.

#. Next, `close the previous milestone`_ (``0.8.7`` for this example).

#. `Create the next milestone`_ (next version PRs will be attached to),
   named "``Docker Autotest Version 0.8.8 (NO API Changes)``", add a description
   and due-date if desired.

#. Move any currently open PRs the new milestone (right side pane of each PRs page).


.. _`Create a new release`: https://github.com/autotest/autotest-docker/releases/new

.. _`Create the next milestone`: https://github.com/autotest/autotest-docker/milestones/new

.. _`close the previous milestone`: https://github.com/autotest/autotest-docker/milestones


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

