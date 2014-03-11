"""
Exception subclasses specific to docker subtests
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

# The exception names don't need docstrings
# pylint: disable=C0111

from autotest.client.shared import error
from ConfigParser import InterpolationError

# Basic exception subclasses (help distinguish if internal raise or not)

class DockerValueError(ValueError):
    pass

class DockerAttributeError(AttributeError):
    pass

class DockerKeyError(KeyError):
    pass

class DockerOSError(OSError):
    pass

class DockerIOError(IOError):
    pass

class DockerConfigError(InterpolationError):
    pass

class DockerNotImplementedError(NotImplementedError):
    pass

# Specific exception subclasses (defined behavior)

class DockerVersionError(DockerValueError):

    def __init__(self, lib_version, config_version):
        self.lib_version = lib_version
        self.config_version = config_version
        super(DockerVersionError, self).__init__()

    def __str__(self):
        return ("Docker test library version %s incompatable with "
                "test configuration version %s.  Likely test code "
                "needs to be updated, to use (possibly) changed "
                "API." % (self.lib_version, self.config_version))

class DockerOutputError(DockerValueError):

    def __init__(self, reason):
        self.reason = reason
        super(DockerOutputError, self).__init__()

    def __str__(self):
        return str(self.reason)

class DockerCommandError(DockerOutputError):
    """Errors coming from within dockercmd module classes"""
    pass

class DockerExecError(error.TestFail):
    """Errors occuring from execution of docker commands"""
    pass

class DockerFullNameFormatError(DockerValueError):
    def __init__(self, name):
        super(DockerFullNameFormatError, self).__init__()
        self.name = name

    def __str__(self):
        return ("Image name %s do not match docker Fully Qualified Image Name"
                " format [registry_hostname[:port]/][user_name/]"
                "(repository_name[:version_tag])" % self.name)
