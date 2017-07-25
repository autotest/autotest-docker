"""
Handler for 'docker info'. Runs command, returns output in
machine-friendly form.
"""

import subprocess


def _normalize(key):
    """
    Storage Driver -> storage_driver
    """
    return key.lower().replace(' ', '_')


class DockerInfo(object):
    """
    Parser of 'docker info' output
    """

    def __init__(self, info_string=None, docker_path=None):
        """
        info_string parameter is for testing only. Do not use in production.
        """
        self._info_string = info_string
        self._info_table = None
        self._docker_path = docker_path

    @property
    def info_string(self):
        """
        Runs 'docker info' and returns output as a flat string.
        (Or, in testing environment, returns the passed-in info_string)
        """
        if self._info_string is None:
            docker = self._docker_path
            if docker is None:
                docker = 'docker'
            self._info_string = subprocess.check_output(docker + ' info',
                                                        shell=True,
                                                        close_fds=True)
        return self._info_string

    @property
    def info_table(self):
        """
        Parses 'docker info' output, returns it as a dict.
        """
        if self._info_table is None:
            self._build_table()
        return self._info_table

    def _build_table(self):
        """
        'docker info' returns a human-readable list of key: value pairs.
        Some are indented by a space, indicating that these key/values
        are subelements of a previous element. To wit:

             Images: 3
             Server Version: 1.12.6
             Storage Driver: devicemapper
              Pool Name: vg--docker-docker--pool
              Pool Blocksize: 524.3 kB
              ...
             Logging Driver: journald

        In this case 'Images', 'Server Version', and 'Logging Driver'
        are simple tuples but 'Storage Driver' has both a value and
        a set of nested key/value pairs: Pool Name, Pool Blocksize, ...

        We parse that and create a dict with the expected key/value
        mapping *and* an extra: for all elements with subelements,
        'element...' (element name plus three dots) is a dict containing
        the subelements. E.g. x['Storage Driver...']['Pool Name'] = 'vg--etc'
        """
        table = {}
        current_key = None
        for line in self.info_string.splitlines():
            # Almost every line will be Foo: Bar, but 'Insecure Registries:'
            # is followed by a simple list of IPv4 netmasks
            if ': ' in line or line.endswith(':'):
                (key, value) = [e.strip() for e in line.split(':', 1)]
            else:
                # No colon. Probably an indented subfield.
                key = line.strip()
                value = ''
            key = _normalize(key)
            if line.startswith(' '):
                if not current_key:
                    raise SyntaxError("docker info: indented line '%s'"
                                      " has no preceding unindented lines."
                                      % line)
                if current_key not in table:
                    table[current_key] = {}
                table[current_key][key] = value
            else:
                table[key] = value
                current_key = key + '...'
        self._info_table = table

    def get(self, key, sub_key=None):
        """
        Fetches and returns the value of a 'docker info' field.
        """
        normalized_key = _normalize(key)
        if sub_key is None:
            return self.info_table[normalized_key]
        sub_fields = self.info_table[normalized_key + '...']
        if not sub_key:
            return sub_fields
        return sub_fields[_normalize(sub_key)]

    def __repr__(self):
        return '{}("{}")'.format(self.__class__.__name__, self.info_string)
