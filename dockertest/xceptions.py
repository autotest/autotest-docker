"""
Exception subclasses specific to docker subtests
"""

from ConfigParser import InterpolationError

# Basic exception subclasses

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

# Specific exception subclasses

class DockerVersionError(DockerValueError):

    def __init__(self, lib_version, config_version):
        self.lib_version = lib_version
        self.config_version = config_version
        super(DockerVersionError, self).__init__()

    def __str__(self):
        return ("Docker test library version %s incompatable with "
                "configuration version %s."
                % (self.lib_version, self.config_version))

class DockerOutputError(DockerValueError):

    def __init__(self, reason):
        self.reason = reason
        super(DockerOutputError, self).__init__()

    def __str__(self):
        return str(self.reason)
