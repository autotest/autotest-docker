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
from autotest.client import utils
from autotest.client.shared import error
from config import Config
from config import none_if_empty
from config import get_as_list
from output import OutputGood, TextTable
from subtestbase import SubBase
from xceptions import DockerTestError, DockerCommandError
from xceptions import DockerFullNameFormatError


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
    repo_split_p = re.compile(r"(?P<repo_addr>.+?"  # optional
                              r"(?P<repo_addr_port>:[\d]+?)?/)?"  # optional
                              r"(?P<user>[\w\-\.\+]+/)?"  # optional
                              r"(?P<repo>[\w\-\.]+)"  # required
                              r"(?P<tag>:[\w\-\.]*)?")  # optional

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
        # docker-1.10 output includes a prefix describing the hash type
        colon = long_id.find(":")
        if colon >= 3:
            self.short_id = long_id[colon + 1:colon + 13]
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

    @classmethod
    def split_to_component(cls, full_name):
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
            full_name = full_name.strip()
            mobj = cls.repo_split_p.match(full_name)
            repo_addr = mobj.group('repo_addr')
            if repo_addr is not None:
                repo_addr = repo_addr.replace('/', '')
            user = mobj.group('user')
            if user is not None:
                user = user.replace('/', '')
            repo = mobj.group('repo')
            tag = mobj.group('tag')
            if tag is not None:
                tag = tag.replace(':', '')
            # Solve the addr/repo vs user/repo case
            if repo_addr is not None and user is None:
                if mobj.group('repo_addr_port') is None:
                    # TODO: try DNS lookup on 'repo_addr' to confirm
                    if repo_addr.find('.') < 0:
                        user = repo_addr
                        repo_addr = None
        except (TypeError, AttributeError):  # no match
            raise DockerFullNameFormatError(full_name)
        return repo, tag, repo_addr, user

    @classmethod
    def full_name_from_component(cls, repo, tag=None,
                                 repo_addr=None, user=None):
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

    @classmethod
    def full_name_from_defaults(cls, config, min_length=4):
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
        fqin = cls.full_name_from_component(
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


class DockerImages(object):

    """
    Docker command supported DockerImage-like instance collection and helpers.

    :param subtest: A subtest.SubBase subclass instance
    :param timeout: A float, seconds to timeout internal operations.
    :param verbose: A boolean, cause internal operations to make more noise.
    """

    #: Allow switching out the class used by items
    DICLS = DockerImage

    #: Operational timeout, may be overridden by subclasses and/or parameters.
    timeout = 60.0

    #: Control verbosity level of operations
    verbose = False

    #: Workaround docker problem of only accepting lower-case image names
    gen_lower_only = True

    #: Run important docker commands output through OutputGood when True
    verify_output = False

    #: Arguments to use when listing images
    images_args = "--no-trunc"

    #: Extra arguments to use with remove methods
    remove_args = None

    def __init__(self, subtest, timeout=None, verbose=False):
        if timeout is None:
            self.timeout = float(subtest.config['docker_timeout'])
        else:
            self.timeout = float(timeout)

        if verbose:
            self.verbose = verbose

        if not isinstance(subtest, SubBase):
            raise DockerTestError("%s is not a SubBase instance."
                                  % subtest.__class__.__name__)
        else:
            self.subtest = subtest

    # private methods don't need docstrings
    @classmethod
    def _di_from_row(cls, row):  # pylint: disable=C0111
        # Translate from row dictionary, to DockerImage parameters
        repo = row['REPOSITORY']
        tag = row['TAG']
        long_id = row['IMAGE ID']
        created = row['CREATED']
        try:
            size = row['VIRTUAL SIZE']
        except KeyError:
            try:
                size = row['SIZE']
            except KeyError:
                raise KeyError("neither SIZE nor VIRTUAL SIZE found in header")
        return cls.DICLS(repo, tag, long_id, created, size)

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

    def full_name_from_defaults(self):
        """
        Return ``DockerImage.full_name_from_defaults(self.subtest.config)``

        **Warning:** This may not be the name from [DEFAULTS] section!
                     for that guarantee, use ``default_image`` attribute
        """
        return self.DICLS.full_name_from_defaults(self.subtest.config)

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

    # Tests may subclass and override this to be stateful, therefor
    # it cannot be defined as a static or class method.
    @property
    def default_image(self):  # pylint: disable=R0201
        """
        Represent the default test image FQIN (guaranteed) from [DEFAULTS]
        """
        cfg = Config()
        defaults = cfg['DEFAULTS']
        # DICLS may have overriden this method
        return DockerImage.full_name_from_defaults(defaults)

    def get_dockerimages_list(self):
        """
        Retrieve list of images using docker CLI

        :note:  This is probably not the method you're looking for,
                try ``list_imgs()`` instead.

        :return: Opaque value, do not use
        """
        cmdresult = self.docker_cmd("images %s" % self.images_args,
                                    self.timeout)
        return self._parse_colums(cmdresult.stdout.strip())

    @staticmethod
    def filter_list_full_name(image_list, full_name=None):
        """
        Return iterable of DockerImage-like instances greedy-matching full_name

        :**Warning**: Do not assume image_list is a python-list!  It can be
                      any object providing the basic iterable and
                      container interfaces.  Similarly, the type of
                      items inside need only be DockerImage-like.

        :param image_list: List of DockerImage instances
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

        :param image_list: List of DockerImage instances
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

        dis = self.list_imgs()
        return [(di.full_name) for di in dis]

    def list_imgs_ids(self):
        """
        Return python-list of **possibly overlapping** 64-character (long)
        image IDs

        :return: **possibly overlapping** [long ID, long ID, ...]
        """

        dis = self.list_imgs()
        return list(set([di.long_id for di in dis]))

    def list_imgs_with_full_name(self, full_name):
        """
        Return python-list of **possibly overlapping** DockerImage-like
        instances greedy-matching full_name.

        :return: **possibly overlapping**
                 [DockerImage-like, DockerImage-like, ...] greedy-matching
                 on full_name (FQIN)
        """

        dis = self.list_imgs()
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

        dis = self.list_imgs()
        return [di for di in dis if di.cmp_greedy(repo, tag, repo_addr, user)]

    def list_imgs_with_image_id(self, image_id):
        """
        Return python-list of **possibly overlapping** 64-character (long)
        image IDs.

        :return: **possibly overlapping**
                 [DockerImage-like, DockerImage-like, ...] greedy-matching
                 on FQIN components.
        """

        dis = self.list_imgs()
        return [di for di in dis if di.cmp_id(image_id)]

    def remove_image_by_id(self, image_id):
        """
        Use docker CLI to removes image matching long or short image_ID.

        :returns: ``autotest.client.utils.CmdResult`` instance
        """

        if self.verify_output:
            dkrcmd = self.docker_cmd_check
        else:
            dkrcmd = self.docker_cmd
        if self.remove_args is not None:
            return dkrcmd("rmi %s %s"
                          % (self.remove_args, image_id), self.timeout)
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
        if self.remove_args is not None:
            return dkrcmd("rmi %s %s"
                          % (self.remove_args, full_name), self.timeout)
        return dkrcmd("rmi %s" % full_name, self.timeout)

    def remove_image_by_image_obj(self, image_obj):
        """
        Remove an image. This is simply a convenience function so
        callers don't need to access image_obj internals.

        :returns: ``autotest.client.utils.CmdResult`` instance
        """
        return self.remove_image_by_id(image_obj.long_id)

    def clean_all(self, fqins):
        """
        Remove all image fqins not configured to preserve

        :param fqins: Iterable sequence of image fqins or IDs
                      (N/B: Only preserve_fquins NAMES are matched)
        """
        if not hasattr(fqins, "__iter__"):
            raise TypeError("clean_all() called with non-iterable.")
        if isinstance(fqins, basestring):
            raise ValueError("clean_all() called with a string, "
                             "instead of an interable of strings.")
        preserve_fqins = self.subtest.config.get('preserve_fqins')
        if preserve_fqins is not None and preserve_fqins.strip() != '':
            preserve_fqins = get_as_list(preserve_fqins)
        else:
            preserve_fqins = []
        preserve_fqins.append(self.default_image)
        preserve_fqins_set = set(preserve_fqins)
        preserve_fqins_set.discard(None)
        preserve_fqins_set.discard('')
        self.verbose = False
        try:
            for name in fqins:
                name = name.strip()
                # Avoid ``docker rmi ''`` or removing a set member
                if not name or name in preserve_fqins_set:
                    continue
                try:
                    self.subtest.logdebug("Cleaning %s", name)
                    self.docker_cmd("rmi --force %s" % name, self.timeout)
                except error.CmdError:
                    continue
        finally:
            self.verbose = self.__class__.verbose
