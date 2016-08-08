"""
Exception subclasses specific to docker subtests
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

# The exception names don't need docstrings
# pylint: disable=C0111

# Some code runs deep, many ancestors actually needed
# pylint: disable=R0901

from ConfigParser import InterpolationError
from autotest.client.shared import error


# Pass-throughs, to help hide autotest.client.shared.error import
class AutotestError(error.AutotestError):

    """Root of most test errors coming from autotest"""
    pass


class DockerCommandError(error.CmdError):

    """Errors coming from within dockercmd module classes"""
    pass


class DockerExecError(error.TestFail):

    """Errors occurring from execution of docker commands"""
    pass


class DockerTestNAError(error.TestNAError):

    """Test skip from execution of docker autotest subtest/subsubtest"""
    pass


class DockerTestError(error.TestError):

    """Code Error in execution of docker autotest subtest/subsubtest"""
    pass


class DockerTestFail(error.TestFail):

    """Test failure in execution of docker autotest subtest/subsubtest"""
    pass

# Basic exception subclasses (help distinguish if internal raise or not)


class DockerValueError(ValueError, AutotestError):
    pass


class DockerAttributeError(AttributeError, AutotestError):
    pass


class DockerKeyError(KeyError, AutotestError):
    pass


class DockerOSError(OSError, AutotestError):
    pass


class DockerIOError(IOError, AutotestError):
    pass


class DockerConfigError(InterpolationError, AutotestError):
    pass


class DockerNotImplementedError(NotImplementedError, AutotestError):
    pass


class DockerRuntimeError(RuntimeError, AutotestError):
    pass

# Specific exception subclasses (defined behavior)


class DockerVersionError(DockerValueError):

    def __init__(self, lib_version=None, config_version=None):
        if lib_version is None:
            lib_version = "Unknown"
        if config_version is None:
            config_version = "Unknown"
        self.lib_version = lib_version
        self.config_version = config_version
        super(DockerVersionError, self).__init__("")

    def __str__(self):
        return ("Docker test library version %s incompatible with "
                "test configuration version %s.  Likely test code "
                "needs to be updated, to use (possibly) changed "
                "API." % (self.lib_version, self.config_version))


class DockerAutotestVersionError(DockerVersionError):

    def __str__(self):
        return ("Installed autotest version %s less "
                "than minimum required version %s, "
                "please update autotest"
                "API." % (self.lib_version, self.config_version))


class DockerOutputError(DockerValueError):

    def __init__(self, reason):
        super(DockerOutputError, self).__init__("")
        self.reason = reason

    def __str__(self):
        return str(self.reason)


class DockerFullNameFormatError(DockerValueError):

    def __init__(self, name):
        super(DockerFullNameFormatError, self).__init__("")
        self.name = name

    def __str__(self):
        return ("Image name %s do not match docker Fully Qualified Image Name"
                " format [registry_hostname[:port]/][user_name/]"
                "(repository_name[:version_tag])" % self.name)


class DockerSubSubtestNAError(DockerTestNAError):

    def __init__(self, child_name):
        super(DockerSubSubtestNAError, self).__init__("")
        self.child_name = child_name

    def __str__(self):
        return ("Sub-subtest %s is not applicable or was disabled"
                % self.child_name)
