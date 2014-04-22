"""
Provides helpers for frequently used docker container operations.

This module defines several independent interfaces using an abstract-base-class
pattern.   They are extended through a few subclasses to meet basic needs.
There is an assumption that the full 64-character long IDs are safer
to use than the short, 12-character ones.  It is also assumed that callers
are in the best position to decide what if any 'tag' content is used
and how to mangle repo/image names.

Where/when ***possible***, both parameters and return values follow this order:

*  ``image_name``
*  ``command``
*  ``ports``
*  ``container_name``
*  ``long_id``
*  ``created``
*  ``status``
*  ``size``
"""

# Pylint runs from another directory, ignore relative import warnings
# pylint: disable=W0403

import json
import re
import signal

from autotest.client import utils
from autotest.client.shared import error
from images import DockerImages

# Many attributes simply required here
class DockerContainer(object):  # pylint: disable=R0902

    """
    Represent a container, image, and command as a set of instance attributes.
    """

    #: There will likely be many instances, limit memory consumption.
    __slots__ = ["image_name", "command", "ports", "container_name",
                 "long_id", "created", "status", "size"]

    def __init__(self, image_name, command, ports=None, container_name=None):
        """
        Create a new container representation based on parameter content.

        :param image_name: FQIN, fully qualified image name
        :param command: String of command container is/was running
        :param ports: String of comma-separated port mappings
        :param container_name: String representing name of container
        """
        self.image_name = image_name
        self.command = command
        self.ports = ports
        self.container_name = str(container_name)
        #: These are typically all generated at runtime
        self.long_id = None
        self.created = None
        self.status = None
        self.size = None

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
        return ("image: %s, command: %s, ports: %s, container_name: %s, "
                "long_id: %s, created: %s, status: %s, size: %s"
                % (self.image_name, self.command, self.ports,
                   self.container_name, self.long_id, self.created,
                   self.status, self.size))

    def __repr__(self):
        """
        Return python-standard representation of instance
        """
        return "DockerContainer(%s)" % str(self)

    def cmp_id(self, container_id):
        """
        Compares long and short version of ID depending on length.

        :param image_id: Exactly 12-character string or longer image ID
        :return: True/False equality
        """
        if len(container_id) == 12:
            return container_id == self.long_id[:12]
        else:
            return container_id == self.long_id

    def cmp_name(self, container_name):
        """
        Compares container_name string value to instance container_name

        :param container_name: Name of a container
        :return: True/False equality
        """
        return self.container_name == str(container_name)


class DockerContainersBase(object):

    """
    Implementation defined collection of DockerContainer-like instances with
    helpers
    """

    # TODO: Add boolean option to run cmdresult through output checkers

    #: Operational timeout, may be overridden by subclasses and/or parameters.
    #: May not be used/enforced equally by all implementations.
    timeout = 60.0

    #: Control verbosity level of operations, implementation may be
    #: subclass-specific.  Actual verbosity level may vary across
    #: implementations.
    verbose = False

    #: Gathering layer-size data is potentially very slow, skip by default
    get_size = True

    def __init__(self, subtest, timeout, verbose):
        """
        Initialize subclass operational instance.

        :param subtest: A subtest.Subtest or subclass instance
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

    # Not defined static on purpose
    def get_container_list(self):  # pylint: disable=R0201
        """
        Standard name for behavior specific to subclass implementation details

        :raises RuntimeError: if not defined by subclass
        """
        raise RuntimeError()

    def list_containers(self):
        """
        Return a python-list of DockerContainer-like instances

        :return: [DockerContainer-like, DockerContainer-like, ...]
        """
        return self.get_container_list()

    def list_containers_with_name(self, container_name):
        """
        Return a python-list of **possibly overlapping** DockerContainer-like
        instances

        :param container_name: String name of container
        :return: Python list of DockerContainer-like instances
        """
        clist = self.list_containers()
        return [cnt for cnt in clist if cnt.cmp_name(container_name)]

    def list_containers_with_cid(self, cid):
        """
        Return a python-list of DockerContainer-like instances

        :param cid: String of long or short container id
        :return: Python list of DockerContainer-like instances
        """
        clist = self.list_containers()
        return [cnt for cnt in clist if cnt.cmp_id(cid)]

    def list_container_ids(self):
        """
        Return python-list of all 64-character (long) container IDs

        :return:  [Cntr ID, Cntr ID, ...]
        """
        dcl = self.get_container_list()
        return [cntr.long_id for cntr in dcl]


    # Not defined static on purpose
    def get_container_metadata(self, long_id):  # pylint: disable=R0201
        """
        Return implementation-specific metadata for container with long_id

        :param long_id: String of long-id for container
        :return: None if long_id invalid/not found or
                 implementation-specific value
        """
        del long_id  # Keep pylint quiet
        return None

    # Disabled by default extension point, can't be static.
    def json_by_long_id(self, long_id):  # pylint: disable=R0201
        """
        Return json-object for container with long_id if supported by
        implementation

        :param long_id: String of long-id for container
        :return: JSON object
        :raises ValueError: on invalid/not found long_id
        :raises RuntimeError: on not supported by implementation
        """
        del long_id  # Keep pylint quiet
        raise RuntimeError()

    def json_by_name(self, container_name):
        """
        Return json-object for container with name if supported by
        implementation

        :param container_name: String name of container
        :return: JSON object
        :raises ValueError: on invalid/not found long_id
        :raises RuntimeError: on not supported by implementation
        """
        cnts = self.list_containers_with_name(str(container_name))
        if len(cnts) == 1:
            return self.json_by_long_id(cnts[0].long_id)
        elif len(cnts) == 0:
            raise ValueError("Container not found with name %s"
                             % container_name)
        else:
            raise ValueError("Multiple containers with name %s found: (%s)"
                             % (container_name, cnts))

    def get_unique_name(self, prefix="", suffix="", length=4):
        """
        Get unique name for a new container
        :param prefix: Name prefix
        :param suffix: Name suffix
        :param length: Length of random string (greater than 1)
        :return: Container name guaranteed to not be in-use.
        """
        assert length > 1
        all_containers = [_.container_name for _ in self.get_container_list()]
        check = lambda name: name not in all_containers
        return utils.get_unique_name(check, prefix, suffix, length)

    def kill_container_by_long_id(self, long_id):
        """
        Use docker CLI 'kill' command on container's long_id

        :param long_id: String of long-id for container
        :param signal:  String of signal name, None for default
        :return: implementation specific value
        :raises RuntimeError: if not supported by implementation
        :raises KeyError: if container not found
        :raises ValueError: if container not running, defunct, or zombie
        """
        raise RuntimeError()

    # TODO: Decide if this should be abstract similar to json_by_long_id
    def kill_container_by_name(self, container_name):
        """
        Use docker CLI 'kill' command on container's long_id, by name lookup.

        :param long_id: String of long-id for container
        :param signal:  String of signal name, None for default
        :return: implementation specific value
        :raises RuntimeError: if not supported by implementation
        :raises KeyError: if container not found
        :raises ValueError: if container not running, defunct, or zombie
        """
        raise RuntimeError()

    # TODO: Add more filter methods

    # Disbled by default extension point, can't be static.
    def remove_by_id(self, container_id):  # pylint: disable=R0201
        """
        Remove an container by 64-character (long) or 12-character
           (short) container ID.

        :raise: RuntimeError when implementation does not permit container
                removal
        :raise: Implementation-specific exception
        :return: Implementation specific value
        """
        del container_id  # keep pylint happy
        raise RuntimeError()
        # Return value is defined as undefined
        return None  # pylint: disable=W0101

    # Disbled by default extension point, can't be static.
    def remove_by_name(self, name):  # pylint: disable=R0201
        """
        Remove an container by container Name.

        :raise: RuntimeError when implementation does not permit container
                removal
        :raise: Implementation-specific exception
        :return: Implementation specific value
        """
        del name  # keep pylint happy
        raise RuntimeError()
        # Return value is defined as undefined
        return None  # pylint: disable=W0101

    def remove_by_obj(self, container_obj):
        """
        Alias for remove_by_id(image_obj.long_id)

        :raise: Same as remove_by_id()
        :raise: Implementation-specific exception
        :return: Same as remove_by_id()
        """
        return self.remove_by_id(container_obj.long_id)


class DockerContainersCLI(DockerContainersBase):

    """
    Docker command supported DockerContainer-like instance collection and
    helpers
    """

    #: Name of signal to send when killing container, None for default
    kill_signal = None

    def __init__(self, subtest, timeout=120, verbose=False):
        super(DockerContainersCLI, self).__init__(subtest,
                                                  timeout,
                                                  verbose)

    # private methods don't need docstrings
    def _get_container_list(self):  # pylint: disable=C0111
        if not self.get_size:
            return self.docker_cmd("ps -a --no-trunc",
                                   self.timeout)
        else:
            return self.docker_cmd("ps -a --no-trunc --size",
                                   self.timeout)

    # private methods don't need docstrings
    def _parse_lines(self, d_psa_stdout):  # pylint: disable=C0111
        clist = []
        lines = d_psa_stdout.strip().splitlines()
        for stdout_line in lines[1:]:  # Skip header
            clist.append(DockerContainersCLI._parse_columns(stdout_line))
        return clist

    # private methods don't need docstrings
    @staticmethod
    def _parse_columns(stdout_line):  # pylint: disable=C0111
        # FIXME: This will break if any column's data contains '  ' anywhere :S
        column_data = re.split("  +", stdout_line)
        return DockerContainersCLI._make_docker_container(column_data)

    # private methods don't need docstrings
    @staticmethod
    def _make_docker_container(column_data):  # pylint: disable=C0111
        jibblets = DockerContainersCLI._parse_jiblets(column_data)
        (long_id, image_name,
         command, created,
         status, portstrs,
         container_name, size) = jibblets
        container = DockerContainer(image_name.strip(),
                                    command.strip(),
                                    portstrs.strip(),
                                    container_name.strip())
        # These are all runtime defined parameters
        container.long_id = long_id.strip()
        container.created = created.strip()
        container.status = status.strip()
        container.size = size.strip()
        return container

    # private methods don't need docstrings
    @staticmethod
    def _parse_jiblets(column_data):  # pylint: disable=C0111
        """
        Content doesn't always fill out all columns, present in standard way.
        """
        if len(column_data) == 8:
            (long_id, image_name, command, created,
             status, portstrs, container_name, size) = column_data
        elif len(column_data) == 7:
            (long_id, image_name, command, created,
             status, container_name, size) = column_data
            portstrs = ""
        elif len(column_data) == 6:
            (long_id, image_name, command, created,
             status, container_name) = column_data
            size = ""
            portstrs = ""
        elif len(column_data) == 12:
            raise ValueError("Baaaawwwwk! What happened to my chickens!")
        else:
            raise ValueError("Error parsing docker ps command output %s"
                             % column_data)
        # Let caller decide which bits are important
        return (long_id, image_name, command, created, status,
                portstrs, container_name, size)

    def docker_cmd(self, cmd, timeout=None):
        """
        Called on to execute docker subcommand cmd with timeout

        :param cmd: Command which should be called using docker
        :param timeout: Override self.timeout if not None
        :return: autotest.client.utils.CmdResult instance
        """
        docker_cmd = ("%s %s" % (self.subtest.config['docker_path'],
                                 cmd))
        if timeout is None:
            timeout = self.timeout
        return utils.run(docker_cmd,
                         verbose=self.verbose,
                         timeout=timeout)

    def get_container_list(self):
        stdout = self._get_container_list().stdout
        return self._parse_lines(stdout)

    def get_container_metadata(self, long_id):
        try:
            cmdresult = self.docker_cmd('inspect "%s"' % str(long_id),
                                        self.timeout)
            if cmdresult.exit_status == 0:
                return json.loads(cmdresult.stdout.strip())
        except (TypeError, ValueError, error.CmdError), details:
            self.subtest.logdebug("docker inspect %s raised: %s: %s",
                                  long_id, details.__class__.__name__,
                                  str(details))
            return None

    def json_by_long_id(self, long_id):
        _json = self.get_container_metadata(long_id)
        if _json is None:
            raise ValueError("Metadata retrieval for container with long_id "
                             "%s not found or not supported" % long_id)
        else:
            return _json

    def kill_container_by_long_id(self, long_id):
        """
        Use docker CLI 'kill' command on container's long_id

        :return: pid of container's process
        """
        # Raise KeyError if not found
        try:
            _json = self.json_by_long_id(long_id)
        except TypeError:  # NoneType object blah blah blah
            raise KeyError("Container %s not found" % long_id)
        pid = _json[0]["State"]["Pid"]
        if not _json[0]["State"]["Running"] or not utils.pid_is_alive(pid):
            raise ValueError("Cannot kill container %s, it is not running,"
                             " or is a defunct or zombie process" % long_id)
        _signal = self.kill_signal
        cmd = 'kill '
        if _signal is not None:
            if _signal.upper().startswith('SIG'):
                _signal = _signal[3:]
            cmd += "--signal=%s " % str(_signal)
        cmd += str(long_id)
        # Raise exception if not exit zero
        self.docker_cmd(cmd)
        return pid

    def kill_container_by_name(self, container_name):
        """
        Use docker CLI 'kill' command on container's long_id, by name lookup.

        :return: pid of container's process
        """
        cntrs = self.list_containers_with_name(str(container_name))
        try:
            return self.kill_container_by_long_id(cntrs[0].long_id)
        except IndexError:
            raise KeyError("Container %s not found" % container_name)

    def remove_by_id(self, image_id):
        """
        Use docker CLI to removes container matching long or short image_ID

        :type args: list of arguments
        :returns: autotest.client.utils.CmdResult instance
        """
        return self.docker_cmd("rm %s" % (image_id), self.timeout)

    def remove_by_name(self, name):
        """
        Remove an containers by Name.

        :type args: list of arguments
        :returns: autotest.client.utils.CmdResult instance
        """
        self.remove_by_id(name, self.timeout)


class DockerContainers(DockerImages):

    """
    Exact same interface-encapsulator as images.DockerImages but for containers
    """

    #: Mapping of interface short-name string to DockerContainersBase subclass.
    interfaces = {'cli': DockerContainersCLI}
