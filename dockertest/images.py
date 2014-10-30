"""
Provides helpers for frequently used docker image/repository operations.

This module defines several independent interfaces using an abstract-base-class
pattern.   They are extended through a few subclasses to meet basic needs.
There is an assumption that the full 64-character long IDs are safer
to use than the short, 12-character ones.  It is also assumed that callers
are in the best position to decide what if any 'tag' content is used
and how to mangle repo/image names.

Where/when ***possible***, both parameters and return values follow this order:

*  ``repo``
*  ``tag``
*  ``long_id``
*  ``created``
*  ``size``
*  ``repo_addr``
*  ``user``

Note: As in other places, the terms 'repo' and 'image' are used
      interchangeably.
"""

# Pylint runs from another directory, ignore relative import warnings
# pylint: disable=W0403

import re
from config import none_if_empty
from autotest.client import utils
from output import OutputGood
from output import TextTable
from subtest import SubBase
from xceptions import DockerFullNameFormatError
from xceptions import DockerCommandError


# Many attributes simply required here
class DockerImage(object):  # pylint: disable=R0902

    """
    Represent a repository or image as a set of instance attributes.
    """

    #: There will likely be many instances, limit memory consumption.
    __slots__ = ["repo_addr", "user", "repo", "tag", "full_name", "long_id",
                 "short_id", "created", "size"]

    #: Regular expression for fully-qualified-image-name (FQIN)
    #: parsing, spec defined in docker-io documentation.  e.g.
    #: ``[registry_hostname[:port]/][user_name/]
    #: (repository_name[:version_tag])``
    repo_split_p = re.compile(r"(.+?(:[\d]+?)?/)?([\w\-\.\+]+/)?"
                              r"([\w\-\.]+)(:[\w\-\.]+)?")

    # Many arguments are simply required here
    # pylint: disable=R0913
    def __init__(self, repo, tag, long_id, created, size,
                 repo_addr=None, user=None):
        """
        Create a new image representation based on parameter content.

        :param repo: String repository name component
        :param tag: String tag name
        :param long_id: Full 64-character ID string for image
        :param created: Opaque instance representing date/time aspect
        :param size: Opaque instance representing a storage-size aspect
        :param repo_addr: Opaque instance representing network address/port
        :param user: String representing username as consumed by usage context
        """

        if repo_addr is None and user is None and tag is None:
            repo, tag, repo_addr, user = self.split_to_component(repo)
        elif repo_addr is None and user is None:
            repo, _, repo_addr, user = self.split_to_component(repo)
        elif repo_addr is None:
            repo, _, repo_addr, _ = self.split_to_component(repo)

        self.repo = repo
        self.tag = tag
        self.long_id = long_id
        self.created = created
        self.size = size
        self.repo_addr = repo_addr
        self.user = user

        self.short_id = long_id[:12]
        self.full_name = self.full_name_from_component(repo, tag,
                                                       repo_addr, user)

    def __eq__(self, other):
        """
        Compare this instance to another

        :param other: An instance of this class (or subclass) for comparison.
        """

        self_val = [getattr(self, name) for name in self.__slots__]
        other_val = [getattr(other, name) for name in self.__slots__]
        for _self, _other in zip(self_val, other_val):
            if _self != _other:
                return False
        return True

    def __str__(self):
        """
        Break down full_name components into a human-readable string
        """

        return ("full_name:%s LONG_ID:%s CREATED:%s SIZE:%s" % (self.full_name,
                                                                self.long_id,
                                                                self.created,
                                                                self.size))

    def __repr__(self):
        """
        Return python-standard representation of instance
        """
        return "DockerImage(%s)" % str(self)

    @staticmethod
    def split_to_component(full_name):
        """
        Split full_name FQIN string into separate component strings

        :Note: Be careful when mixing ``repo_addr`` and ``user`` name, as
               there could be content-dependent side-effects.

        :param full_name: FQIN, Fully Qualified Image Name
        :return: Iterable of repo, tag, repo_addr, user strings
        """
        if full_name is None:
            return None, None, None, None
        try:
            (repo_addr, _, user,  # ignore optional port sub-group value
             repo, tag) = DockerImage.repo_split_p.match(full_name).groups()
            if repo_addr:
                repo_addr = repo_addr[:-1]  # remove trailing slash
            if user:
                user = user[:-1]  # remove trailing slash
            if tag:
                tag = tag[1:]  # remove beginning colon
        except TypeError:  # no match
            raise DockerFullNameFormatError(full_name)
        return repo, tag, repo_addr, user

    @staticmethod
    def full_name_from_component(repo, tag=None, repo_addr=None, user=None):
        """
        Fully form a name (FQIN) based on individual components.

        :param repo: String repository name component
        :param tag: Optional tag name string
        :param repo_addr: String representing network address/port
        :param user: String representing username as consumed by usage context
        :return:  FQIN string, Fully Qualified Image Name
        """

        component = zip(("%s/", "%s/", "%s", ":%s"),
                        (repo_addr, user, repo, tag))
        return "".join([c % v for c, v in component if v is not None])

    @staticmethod
    def full_name_from_defaults(config, min_length=4):
        """
        Return the FQIN based on '[DEFAULT]' options

        :param config: Dict-like containing keys: ``docker_repo_name``,
                       ``docker_repo_tag``, ``docker_registry_host``,
                       ``docker_registry_user``
        :param min_length: Minimum length of full name, raise ValueError
                           if less.
        :return: Fully Qualified Image Name string.
        """

        # Don't modify actual data
        config = config.copy()
        for key in ('docker_repo_name', 'docker_repo_tag',
                    'docker_registry_host', 'docker_registry_user'):
            none_if_empty(config, key)
        fqin = DockerImage.full_name_from_component(
            config['docker_repo_name'],
            config['docker_repo_tag'],
            config['docker_registry_host'],
            config['docker_registry_user'])
        if len(fqin) < min_length:
            raise ValueError("Unable to search image with FQIN '%s',"
                             "please check values in configuration"
                             " (defaults.ini) [docker_repo_name: %s,"
                             " docker_repo_tag: %s, docker_registry_host: %s,"
                             " docker_registry_user: %s]" %
                             (fqin,
                              config['docker_repo_name'],
                              config['docker_repo_tag'],
                              config['docker_registry_host'],
                              config['docker_registry_user']))
        return fqin

    def cmp_id(self, image_id):
        """
        Compares long and short version of ID depending on length.

        :param image_id: Exactly 12-character string or longer image ID
        :return: True/False equality
        """

        if len(image_id) == 12:
            return image_id == self.short_id
        else:
            return image_id == self.long_id

    def cmp_full_name_with_component(self, repo, tag=None,
                                     repo_addr=None, user=None):
        """
        Boolean compare instance's full_name to individual components

        :param repo: String repository name component
        :param tag: Optional tag name string
        :param repo_addr: Optional String representing network address/port
        :param user: Optional string username as consumed by usage context
        :return: True/False on equality
        """

        return self.full_name == self.full_name_from_component(repo,
                                                               tag,
                                                               repo_addr,
                                                               user)

    def cmp_full_name(self, full_name):
        """
        Compare instance's full_name to full_name parameter

        :param full_name: FQIN string, Fully Qualified Image Name
        :return: True/False on equality
        """

        return self.full_name == full_name

    def cmp_greedy(self, repo=None, tag=None, repo_addr=None, user=None):
        """
        Boolean compare instance full_name's components to Non-None arguments

        example:

        ::

            i_1 = DockerImage('repo', None, None, None, 42, None, None)
            i_1.cmp_greedy('repo', 'tag', 'example.com', 'billy')
            False

            i_2 = DockerImage('repo', 'tag', None, None, None,
                              'example.com', 'billy')
            i_2.cmp_greedy('repo', None, None, None)
            True

        :param repo: String repository name component
        :param tag: Optional tag name string
        :param repo_addr: Optional String representing network address/port
        :param user: Optional string username as consumed by usage context
        :return: True/false on all Non-None argument equality to instance
        """

        if repo is not None and repo != self.repo:
            return False
        if tag is not None and tag != self.tag:
            return False
        if repo_addr is not None and repo_addr != self.repo_addr:
            return False
        if user is not None and user != self.user:
            return False
        return True

    def cmp_greedy_full_name(self, full_name):
        """
        Compare instance full_name's components to Non-None full_name
        components

        :param full_name: FQIN string, Fully Qualified Image Name
                          possibly containing
        :return: True/false on all Non-None full_name components equality
                 to instance
        """

        (repo, tag, repo_addr, user) = self.split_to_component(full_name)
        return self.cmp_greedy(repo, tag, repo_addr, user)


class DockerImagesBase(object):

    """
    Implementation defined collection of DockerImage-like instances with
    helpers
    """

    #: Operational timeout, may be overridden by subclasses and/or parameters.
    #: May not be used/enforced equally by all implementations.
    timeout = 60.0

    #: Control verbosity level of operations, implementation may be
    #: subclass-specific.  Actual verbosity level may vary across
    #: implementations.
    verbose = False

    #: Workaround docker problem of only accepting lower-case image names
    gen_lower_only = True

    def __init__(self, subtest, timeout, verbose):
        """
        Initialize subclass operational instance.

        :param subtest: A subtest.SubBase subclass instance
        :param timeout: An opaque non-default timeout value to use on instance
        :param verbose: A boolean non-default verbose value to use on instance
        """

        if timeout is None:
            # Defined in [DEFAULTS] guaranteed to exist
            self.timeout = subtest.config['docker_timeout']
        else:
            # config() auto-converts otherwise catch non-float convertible
            self.timeout = float(timeout)

        if verbose:
            self.verbose = verbose

        self.subtest = subtest

    def get_unique_name(self, prefix="", suffix="", length=4):
        """
        Get unique name for a new image
        :param prefix: Name prefix
        :param suffix: Name suffix
        :param length: Length of random string (greater than 1)
        :return: Image name guaranteed to not be in-use.
        """

        assert length > 1
        if prefix:
            _name = "%s_%s_%%s" % (self.subtest.__class__.__name__, prefix)
        else:
            _name = "%s_%%s" % self.subtest.__class__.__name__
        all_images = self.list_imgs_full_name()
        if suffix:
            _name += suffix
        for _ in xrange(1000):
            name = _name % utils.generate_random_string(length)
            if self.gen_lower_only:
                name = name.lower()
            if name not in all_images:
                return name

    @property
    def default_image(self):
        """
        Represent the default test image FQIN based on subtest configuration
        """
        return DockerImage.full_name_from_defaults(self.subtest.config)

    # Not defined static on purpose
    def get_dockerimages_list(self):    # pylint: disable=R0201
        """
        Standard name for behavior specific to subclass implementation details

        :note:  This is probably not the method you're looking for,
                try ``list_imgs()`` instead.

        :raise RuntimeError: if not defined by subclass
        :return: **implementation-specific**
        """

        raise RuntimeError()

    @staticmethod
    def filter_list_full_name(image_list, full_name=None):
        """
        Return iterable of DockerImage-like instances greedy-matching full_name

        :**Warning**: Do not assume image_list is a python-list!  It can be
                      any object providing the basic iterable and
                      container interfaces.  Similarly, the type of
                      items inside need only be DockerImage-like.

        :param image_list: Opaque, iterable, container-like, specific
                           to subclass implementation.
        :param full_name: FQIN string, Fully Qualified Image Name
        :return: Iterable container-like of DockerImage-like instances
        """

        return [di for di in image_list if di.cmp_greedy_full_name(full_name)]

    @staticmethod
    def filter_list_by_components(image_list, repo=None, tag=None,
                                  repo_addr=None, user=None):
        """
        Return iterable of DockerImage-like instances greedy-matching full_name

        :**Warning**: Do not assume image_list is a python-list!  It can be
                      any object providing the basic iterable and
                      container interfaces.  Similarly, the type of
                      items inside need only be DockerImage-like.

        :param image_list: Opaque, iterable, container-like, specific
                           to subclass implementation.
        :param repo: String repository name component
        :param tag: Optional tag name string
        :param repo_addr: String representing network address/port
        :param user: String representing username as consumed by usage context
        :return: Iterable of **possibly overlapping** DockerImage-like
                 instances
        """

        return [di for di in image_list if di.cmp_greedy(repo, tag,
                                                         repo_addr, user)]

    def list_imgs(self):
        """
        Return a python-list of DockerImage-like instances

        :return: **possibly overlapping**
                 [DockerImage-like, DockerImage-like, ...]
        """

        return self.get_dockerimages_list()

    def list_imgs_full_name(self):
        """
        Return python-list of Fully Qualified Image Name strings

        :return: **non-overlapping** [FQIN, FQIN, ...]
        """

        dis = self.get_dockerimages_list()
        return [(di.full_name) for di in dis]

    def list_imgs_ids(self):
        """
        Return python-list of **possibly overlapping** 64-character (long)
        image IDs

        :return: **possibly overlapping** [long ID, long ID, ...]
        """

        dis = self.get_dockerimages_list()
        return list(set([di.long_id for di in dis]))

    def list_imgs_with_full_name(self, full_name):
        """
        Return python-list of **possibly overlapping** DockerImage-like
        instances greedy-matching full_name.

        :return: **possibly overlapping**
                 [DockerImage-like, DockerImage-like, ...] greedy-matching
                 on full_name (FQIN)
        """

        dis = self.get_dockerimages_list()
        return [di for di in dis if di.cmp_greedy_full_name(full_name)]

    # Extra verbosity in name is needed here
    # pylint: disable=C0103
    def list_imgs_with_full_name_components(self, repo=None,
                                            tag=None,
                                            repo_addr=None,
                                            user=None):
        """
        Return python-list of **possibly overlapping** DockerImage-like
        instances greedy-matching FQIN components.

        :return: **possibly overlapping**
                 [DockerImage-like, DockerImage-like, ...] greedy-matching
                 on FQIN components.
        """

        dis = self.get_dockerimages_list()
        return [di for di in dis if di.cmp_greedy(repo, tag, repo_addr, user)]

    def list_imgs_with_image_id(self, image_id):
        """
        Return python-list of **possibly overlapping** 64-character (long)
        image IDs.

        :return: **possibly overlapping**
                 [DockerImage-like, DockerImage-like, ...] greedy-matching
                 on FQIN components.
        """

        dis = self.get_dockerimages_list()
        return [di for di in dis if di.cmp_id(image_id)]

    # Disabled by default extension point, can't be static.
    def remove_image_by_id(self, image_id):  # pylint: disable=R0201
        """
        Remove image by 64-character (long) or 12-character (short) image ID.

        :raise RuntimeError: when implementation does not permit image removal
        :return: Implementation specific value
        """
        # FIXME: This should raise Implementation-independant exceptions
        #        for common conditions, otherwise caller is locked to
        #        implementation-specific exceptions :(
        del image_id  # keep pylint happy
        raise RuntimeError()

    # Disabled by default extension point, can't be static.
    def remove_image_by_full_name(self, full_name):  # pylint: disable=R0201
        """
        Remove an image by FQIN Fully Qualified Image Name.

        :raise RuntimeError: when implementation does not permit image removal
        :return: Implementation specific value
        """
        # FIXME: This should raise Implementation-independant exceptions
        #        for common conditions, otherwise caller is locked to
        #        implementation-specific exceptions :(
        del full_name  # keep pylint happy
        raise RuntimeError()

    def remove_image_by_image_obj(self, image_obj):
        """
        Alias for remove_image_by_full_name(image_obj.full_name)

        :raise RuntimeError: when implementation does not permit image removal
        :return: Same as remove_image_by_full_name()
        """
        # FIXME: This should raise Implementation-independant exceptions
        #        for common conditions, otherwise caller is locked to
        #        implementation-specific exceptions :(
        return self.remove_image_by_full_name(image_obj.full_name)


class DockerImagesCLI(DockerImagesBase):

    """
    Docker command supported DockerImage-like instance collection and helpers.
    """

    #: Run important docker commands output through OutputGood when True
    verify_output = False

    #: Arguments to use when listing images
    images_args = "--no-trunc"

    def __init__(self, subtest, timeout=None, verbose=False):
        super(DockerImagesCLI, self).__init__(subtest,
                                              timeout,
                                              verbose)

    @staticmethod
    def _di_from_row(row):
        # Translate from row dictionary, to DockerImage parameters
        repo = row['REPOSITORY']
        tag = row['TAG']
        long_id = row['IMAGE ID']
        created = row['CREATED']
        size = row['VIRTUAL SIZE']
        return DockerImage(repo, tag, long_id, created, size)

    # private methods don't need docstrings
    def _parse_colums(self, stdout_strip):  # pylint: disable=C0111
        texttable = TextTable(stdout_strip)
        return [self._di_from_row(row) for row in texttable]

    def docker_cmd(self, cmd, timeout=None):
        """
        Called on to execute the docker command cmd with timeout.

        :param cmd: Command which should be called using docker
        :param timeout: Override self.timeout if not None
        :return: ``autotest.client.utils.CmdResult`` instance
        """

        docker_image_cmd = ("%s %s" % (self.subtest.config['docker_path'],
                                       cmd))
        if timeout is None:
            timeout = self.timeout
        from autotest.client.shared.error import CmdError
        try:
            return utils.run(docker_image_cmd,
                             verbose=self.verbose,
                             timeout=timeout)
        except CmdError, detail:
            raise DockerCommandError(detail.command, detail.result_obj,
                                     additional_text=detail.additional_text)

    def docker_cmd_check(self, cmd, timeout=None):
        """
        Wrap docker_cmd, running result through OutputGood before returning
        """

        result = self.docker_cmd(cmd, timeout)
        OutputGood(result)
        return result

    def get_dockerimages_list(self):
        cmdresult = self.docker_cmd("images %s" % self.images_args,
                                    self.timeout)
        return self._parse_colums(cmdresult.stdout.strip())

    def remove_image_by_id(self, image_id):
        """
        Use docker CLI to removes image matching long or short image_ID.

        :returns: ``autotest.client.utils.CmdResult`` instance
        """

        if self.verify_output:
            dkrcmd = self.docker_cmd_check
        else:
            dkrcmd = self.docker_cmd
        return dkrcmd("rmi %s" % image_id, self.timeout)

    def remove_image_by_full_name(self, full_name):
        """
        Remove an image by FQIN Fully Qualified Image Name.

        :returns: ``autotest.client.utils.CmdResult`` instance
        """

        if self.verify_output:
            dkrcmd = self.docker_cmd_check
        else:
            dkrcmd = self.docker_cmd
        return dkrcmd("rmi %s" % full_name, self.timeout)


class DockerImages(object):

    """
    Encapsulates ``DockerImage`` interfaces for manipulation of docker images.
    """

    #: Mapping of interface short-name string to DockerImagesBase subclass.
    #: (shortens line-length when instantiating)
    interfaces = {"cli": DockerImagesCLI}

    def __init__(self, subtest, interface_name="cli",
                 timeout=None, verbose=False):
        """
        Execute docker subcommand with arguments and a timeout.

        :param subtest: A subtest.SubBase subclass instance
        :param interface_name: Class-defined string representing a
                               DockerImagesBase subclass
        :param timeout: Operational timeout override specific to interface
        :param verbose: Operational verbose override specific to interface
        """
        # Prevent accidental test.test instance passing
        if not isinstance(subtest, SubBase):
            raise TypeError("Instance %s is not a SubBase or "
                            "subclass instance." % str(subtest))
        _dic = self.interfaces[interface_name]
        super(DockerImages, self).__setattr__('_interface',
                                              _dic(subtest, timeout, verbose))

    def __getattr__(self, name):
        """
        Hide interface choice while allowing attribute/method access.

        :return: attribute/method provided by interface implementation.
        """

        return getattr(self._interface, name)

    def __setattr__(self, name, value):
        """
        Hide interface choice while allowing attribute/method access.

        :return: attribute/method provided by interface implementation.
        """
        if hasattr(self._interface, name):
            return setattr(self._interface, name, value)
        else:
            super(DockerImages, self).__setattr__(name, value)

    @property
    def interface(self):
        """
        Interface class being encapsulated (read-only property)
        """

        return self._interface.__class__

    @property
    def interface_name(self):
        """
        Class name of interface being encapsulated (read-only property)
        """

        return self.interface.__name__

    @property
    def interface_shortname(self):
        """
        Short-name used to create this instance (read-only property)
        """

        keys = self.interfaces.keys()
        values = self.interfaces.values()
        try:
            return keys[values.index(self.interface)]
        except ValueError, detail:
            raise KeyError(detail)
