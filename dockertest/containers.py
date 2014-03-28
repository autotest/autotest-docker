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

import re
import json
from autotest.client.shared import error
from autotest.client import utils
from output import OutputGood
from images import DockerImages

# Many attributes simply required here
class DockerContainer(object): # pylint: disable=R0902
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
        #: Theese are typically all generated at runtime
        self.long_id = None
        self.created = None
        self.status = None
        self.size = None

    def __eq__(self, other):
        """
        Compare this instance to another
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

    #: Operational timeout, may be overridden by subclasses and/or parameters.
    #: May not be used/enforced equally by all implementations.
    timeout = 60.0

    #: Control verbosity level of operations, implementation may be
    #: subclass-specific.  Actual verbosity level may vary across
    #: implementations.
    verbose = False

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

        :raise: RuntimeError if not defined by subclass
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

    # Not defined static on purpose
    def get_container_metadata(self, long_id):  # pylint: disable=R0201
        """
        Return implementation-specific metadata for container with long_id

        :param long_id: String of long-id for container
        :return: None if long_id invalid/not found or
                 implementation-specific value
        """
        del long_id  #  Keep pylint quiet
        return None

    # Disbled by default extension point, can't be static.
    def json_by_long_id(self, long_id):  # pylint: disable=R0201
        """
        Return json-object for container with long_id if supported by
        implementation

        :param long_id: String of long-id for container
        :return: JSON object
        :raise ValueError: on invalid/not found long_id
        :raise RuntimeError: on not supported by implementation
        """
        del long_id  #  Keep pylint quiet
        raise RuntimeError()

    def json_by_name(self, container_name):
        """
        Return json-object for container with name if supported by
        implementation

        :param container_name: String name of container
        :return: JSON object
        :raise ValueError: on invalid/not found long_id
        :raise RuntimeError: on not supported by implementation
        """
        cnts = self.list_containers_with_name(str(container_name))
        if len(cnts) == 1:
            return self.json_by_long_id(cnts[0].long_id)
        else:
            raise ValueError("Container not found with name %s"
                             % container_name)

    def get_unique_name(self, prefix="", suffix="", length=4):
        """
        Get unique name for a new container
        :param prefix: Name prefix
        :param suffix: Name suffix
        :param length: Length of random string.
        :return: Unique name according to check function
        """
        assert length > 1
        all_containers = [_.container_name for _ in self.get_container_list()]
        check = lambda name: name not in all_containers
        return utils.get_unique_name(check, prefix, suffix, length)

    # TODO: Add more filter methods

    # TODO: Add 'rm' abstract methods

class DockerContainersCLI(DockerContainersBase):
    """
    Docker command supported DockerContainer-like instance collection and
    helpers
    """

    def __init__(self, subtest, timeout=120, verbose=False):
        super(DockerContainersCLI, self).__init__(subtest,
                                                  timeout,
                                                  verbose)

    # private methods don't need docstrings
    def _get_container_list(self):  # pylint: disable=C0111
        return self.docker_cmd("ps -a --no-trunc --size",
                               self.timeout)

    # private methods don't need docstrings
    @staticmethod
    def _parse_lines(d_psa_stdout):  # pylint: disable=C0111
        clist = []
        lines = d_psa_stdout.strip().splitlines()
        for stdout_line in lines[1:]: # Skip header
            clist.append(DockerContainersCLI._parse_columns(stdout_line))
        return clist

    # private methods don't need docstrings
    @staticmethod
    def _parse_columns(stdout_line):  # pylint: disable=C0111
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
        elif len(column_data) == 12:
            raise ValueError("Baaaawwwwk! What happened to my chickens!")
        else:
            raise ValueError("Error parsing docker ps command output")
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

    # TODO: Decide if this should be abstract similar to json_by_long_id
    def kill_container_by_long_id(self, long_id, signal=None):
        """
        Use docker CLI 'kill' command on container's long_id

        :param long_id: String of long-id for container
        :param signal:  String of signal name, None for default
        :return: pid of container's process
        :raise: KeyError if container not found
        :raise: ValueError if container not running, defunct, or zombie
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
        cmd = 'kill'
        if signal is not None:
            if signal.upper().startswith('SIG'):
                signal = signal[3:]
            cmd += " --signal=%s " % str(signal)
        cmd += str(long_id)
        # Raise exception if not exit zero
        self.docker_cmd(cmd)
        return pid

    # TODO: Decide if this should be abstract similar to json_by_long_id
    def kill_container_by_name(self, container_name, signal=None):
        """
        Use docker CLI 'kill' command on container's long_id, by name lookup.

        :param long_id: String of long-id for container
        :param signal:  String of signal name, None for default
        :return: pid of container's process
        :raise: KeyError if container not found
        :raise: ValueError if container not running, defunct, or zombie
        """
        cntrs = self.list_containers_with_name(str(container_name))
        # Raise KeyError if not found
        return self.kill_container_by_long_id(cntrs[0].long_id, signal)


class DockerContainersCLICheck(DockerContainersCLI):
    """
    Extended DockerContainersCLI for passing test options and checking output
    """

    #: This is probably test-subject related, be a bit more noisy
    verbose = True

    def docker_cmd(self, cmd, timeout=None):
        cmdresult = super(DockerContainersCLICheck,
                          self).docker_cmd(cmd, timeout)
        # Throws exception if checks fail
        OutputGood(cmdresult)
        return cmdresult


class DockerContainers(DockerImages):
    """
    Exact same interface-encapsulator as images.DockerImages but for containers
    """

    #: Mapping of interface short-name string to DockerContainersBase subclass.
    interfaces = {'cli':DockerContainersCLI, 'clic':DockerContainersCLICheck}
