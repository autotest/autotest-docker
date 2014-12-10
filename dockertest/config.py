"""
Extension of standard ConfigParser.SafeConfigParser abstracting section names.

The ``Config`` class is the main thing here intended for consumption. Possibly
the ``none_if_empty`` function as well.  Everything else is available, and
unit-tested but not intended for wide-spread general use.
"""

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

from ConfigParser import SafeConfigParser, Error, NoOptionError
from collections import MutableMapping
import os.path
import sys
import copy

import xceptions


#: Absolute path to directory containing this module
MYDIR = os.path.dirname(sys.modules[__name__].__file__)

#: Parent directory of directory containing this module
PARENTDIR = os.path.dirname(MYDIR)

#: Directory path relative to PARENTDIR containing default config files
CONFIGDEFAULT = os.path.join(PARENTDIR, 'config_defaults')

#: Directory path relative to PARENTDIR containing customized config files.
CONFIGCUSTOMS = os.path.join(PARENTDIR, 'config_custom')

#: Durectiry path relative to CONFIGDIR containing default config files
DEFAULTSUBDIR = 'defaults'

#: Name of file holding special DEFAULTS section and options
DEFAULTSFILE = 'defaults.ini'

#: Name of file holding special control script options
CONTROLFILE = 'control.ini'


class ConfigSection(object):

    """
    Wraps SafeConfigParser with static section handling

    :param defaults: dict-like containing default keys/values
    :param section: name of section to initially bind to

    :note: Not an exact interface reproduction, some functionality
           left out!
    """

    def __init__(self, defaults, section):
        self._section = section
        # SafeConfigParser is old-style, and we're changing method parameters
        self._scp = SafeConfigParser(defaults)
        self._scp.add_section(self._section)

    def defaults(self):
        """
        Returns dictionary of default options
        """
        return self._scp.defaults()

    def sections(self):
        """
        Returns a list containing this instances section-name
        """
        return [self._section]

    def add_section(self, section):
        """
        Not written, do not use!

        :raises NotImplementedError: DO NOT USE!
        """
        raise NotImplementedError()

    def has_section(self, section):
        """
        Returns True if instance-section == ``section``

        :param section: Name of section to check.
        :returns: True/False if section exists.
        """
        if section == self._section:
            return True
        else:
            return False

    def options(self):
        """
        Returns dictionary of all options keys/values
        """
        return self._scp.options(self._section)

    def has_option(self, option):
        """
        Returns True if key-named ``option`` exists

        :param option: Name of the option (key) to check.
        :returns: True/False if option (key) exists.
        """
        return self._scp.has_option(self._section, option)

    # Private method doesn't need docstring
    def _prune_sections(self):  # pylint: disable=C0111
        for section in self._scp.sections():
            if section != self._section:
                self._scp.remove_section(section)

    def read(self, filenames):
        """
        Replace current contents with content from filename(s)/list

        :param filenames: Same as for ``SafeConfigParser.read`` method
        :return: List of successfully parsed filenames.
        """
        result = self._scp.read(filenames)  # Changes self._scp
        self._prune_sections()
        return result

    # Short name 'fp' mirrors use in ConfigParser module
    def readfp(self, fp, filename=None):  # pylint: disable=C0103
        """
        Replace current contents with content from file

        :param fp: Same as for ``SafeConfigParser.readfp`` method
        :param filename: Same as for ``SafeConfigParser.readfp`` method
        :return:  Same as for ``SafeConfigParser.readfp`` method
        """
        result = self._scp.readfp(fp, filename)  # Changes self._scp
        self._prune_sections()
        return result

    def get(self, option):
        """
        Return value assigned to key named ``option``

        :param option: Name of the ``option`` (key) to check.
        :returns: The value assigned to ``option``
        """
        return self._scp.get(self._section, option)

    def getint(self, option):
        """
        Convert/Return value assigned to key named ``option``

        :param option: Name of the ``option`` (key) to check.
        :return: Value assigned to ``option`` converted to an integer.
        """
        return self._scp.getint(self._section, option)

    def getfloat(self, option):
        """
        Convert/Return value assigned to key named ``option``

        :param option: Name of the ``option`` (key) to check.
        :return: Value assigned to ``option`` converted to a float.
        """
        return self._scp.getfloat(self._section, option)

    def getboolean(self, option):
        """
        Convert/Return value assigned to key named ``option``

        :param option: Name of the ``option`` (key) to check.
        :return: ``True``: if value is ``yes``, ``true``. ``False`` if ``no``
                           or ``false``.
        """
        try:
            value = self._scp.get(self._section, option).lower().strip()
            positives = ("yes", "true")
            negatives = ("no", "false")
            if value in positives:
                return True
            if value in negatives:
                return False
            # try regular way
        except AttributeError:
            pass  # try regular way
        return self._scp.getboolean(self._section, option)

    def set(self, option, value):
        """
        Set value assigned to key named ``option``

        :param option: Name of the ``option`` (key) to set.
        :param value: Content to assign to ``option``.
        :return: Same as for ``SafeConfigParser.set`` method.
        """
        return self._scp.set(self._section, option, str(value))

    def write(self, fileobject):
        """
        Overwrite current contents of ``fileobject.name``
        """
        return self._scp.write(open(fileobject.name, "wb"))

    def merge_write(self, fileobject):
        """
        Update section contents of ``fileobject.name`` by section only.
        """
        scp = SafeConfigParser()
        # Safe if file doesn't exist
        scp.read(fileobject.name)
        if not scp.has_section(self._section):
            scp.add_section(self._section)
        for key, value in self.items():
            scp.set(self._section, key, value)
        scp.write(open(fileobject.name, "w+b"))  # truncates file first

    def remove_option(self, option):
        """
        Remove option-key ``option``
        """
        return self._scp.remove_option(self._section, option)

    def remove_section(self):
        """
        Not implemented, do not use!

        :raises NotImplementedError: DO NOT USE!
        """
        raise NotImplementedError()

    def items(self):
        """
        Return list of ``key``/``value`` tuples for contents
        """
        return self._scp.items(self._section)


class ConfigDict(MutableMapping):

    r"""
    Dict-like ``ConfigSection`` interface, ``SafeConfigParser`` facade.

    :param section: Section name string to represent
    :param defaults: dict-like of default parameters (lower-case keys)
    :param \*args:  Passed through to dict-like super-class.
    :param \*\*dargs:  Passed through to dict-like super-class.
    """

    def __init__(self, section, defaults=None, *args, **dargs):
        self._config_section = ConfigSection(defaults=defaults,
                                             section=section)
        super(ConfigDict, self).__init__(*args, **dargs)

    # Private method doesn't need docstring
    def _keyset(self):  # pylint: disable=C0111
        mine = set([val.lower()
                    for val in self._config_section.options()])
        default = set([val.lower()
                       for val in self._config_section.defaults().keys()])
        complete = mine | default
        return complete

    def __len__(self):
        return len(self._keyset())

    def __iter__(self):
        return (option for option in self._keyset())

    def __contains__(self, item):
        return item.lower() in self._keyset()

    def __getitem__(self, key):
        # ConfigParser forces this, force it so any errors are clear
        key = key.lower()
        # Don't call more methods than necessary
        if not self.__contains__(key):
            raise xceptions.DockerKeyError(key)
        # No suffix calls regular get(), boolean wants to gobble '0' and '1' :(
        for suffix in ('int', 'boolean', 'float', ''):
            method = getattr(self._config_section, 'get%s' % suffix)
            try:
                return method(key)
            except (ValueError, AttributeError):
                continue
        raise xceptions.DockerConfigError('', '', key)

    def __setitem__(self, key, value):
        return self._config_section.set(key, str(value))

    def __delitem__(self, key):
        return self._config_section.remove_option(key)

    def read(self, filelike):
        """Load configuration from file-like object filelike"""
        filelike.seek(0)
        return self._config_section.readfp(filelike)

    @staticmethod
    def write(filelike):
        """Raise an IOError exception, instance is read-only"""
        raise xceptions.DockerIOError("Instance does not permit writing to %s"
                                      % filelike.name)


class Config(dict):

    r"""
    Global dict-like of dict-like(s) per section with defaulting values.

    :param \*args: Same as built-in python ``dict()`` params.
    :param \*\*dargs: Same as built-in python ``dict()`` params.
    :return: Regular 'ole python dictionary of global config also as
             python dictionaries (cached on first load)
    """
    #: Public instance attribute cache of defaults parsing w/ non-clashing name
    defaults_ = None
    #: Public instance attribute cache of configs parsing w/ non-clashing name
    configs_ = None
    #: private class-attribute cache used to return copy as a dict in __new__()
    _singleton = None
    #: prepared dict for deep copy.
    prepdict = None

    def __new__(cls, *args, **dargs):
        if cls._singleton is None:
            # Apply *args, *dargs _after_ making deep-copy
            cls._singleton = dict.__new__(cls)
            if cls._singleton.prepdict is None:
                cls._singleton.prepdict = cls._singleton.copy()
        deep_copy = copy.deepcopy(cls._singleton.prepdict)
        deep_copy.update(dict(*args, **dargs))
        # Prevent any modifications from affecting cache and/or other tests
        return deep_copy

    @property
    def defaults(self):
        """
        Read-only cached defaults.ini DEFAULTS section options as a dict.
        """
        if self.__class__.defaults_ is None:
            defaults_ = SafeConfigParser()
            default_defaults = os.path.join(CONFIGDEFAULT, DEFAULTSFILE)
            custom_defaults = os.path.join(CONFIGCUSTOMS, DEFAULTSFILE)
            try:
                defaults_.read(custom_defaults)
                # Dump out all DEFAULTS section options into a dict. & cache it
                self.__class__.defaults_ = dict(defaults_.items('DEFAULTS'))
            except (IOError, Error):
                defaults_.read(default_defaults)
                self.__class__.defaults_ = dict(defaults_.items('DEFAULTS'))
            # Drop options not used by docker autotest
            for option in list(self.__class__.defaults_.keys()):
                if option.startswith('envcheck_'):
                    del self.__class__.defaults_[option]
        # Return CACHED defaults dictionary
        return self.__class__.defaults_

    @staticmethod
    def load_config_sec(scp, newcd, section, configs_dict, defaults_dict):
        """
        Load parsed contents and process __example__ options.

        :param scp: ``SafeConfigParser`` instance loaded with content
        :param newcd: New ``ConfigDict`` instance loaded with content
        :param section: Name of section to process.
        :param configs_dict: Destination dict-like to store result
        :param defaults_dict: Dict-like containing all default option/values.
        """
        def_warn = defaults_dict.get('__example__', '').lower()
        if def_warn is not '':
            def_warn = set(get_as_list(def_warn))
        else:
            def_warn = set()
        # Need to detect __example__ options that differ w/ existing
        old_sec = configs_dict[section]
        configs_dict[section] = newcd  # incoming, overriding section
        # reference from scp, it does not know/inherit defaults
        try:
            sec_warn = scp.get(section, '__example__').lower()
            if sec_warn is not '':
                sec_warn = set(get_as_list(sec_warn))
            else:
                sec_warn = set()
        except NoOptionError:
            sec_warn = set()
        sec_warn |= def_warn  # re-combine with global DEFAULTS
        if None in sec_warn:
            sec_warn.remove(None)
        if '' in sec_warn:
            sec_warn.remove('')
        # Discard examples for options that were modified from original
        for warn_option in set(sec_warn):  # work from copy
            # allow keyerror if undefined option in __example__
            former_value = old_sec.get(warn_option)
            currnt_value = newcd.get(warn_option)
            if currnt_value != former_value:
                sec_warn.remove(warn_option)  # change was made
            # else, contents unmodified, allow example through
        # Re-form it back into a CSV
        if len(sec_warn) > 0:
            newcd['__example__'] = ', '.join(sec_warn)
        else:
            # Everything overriden, prevent defaults creeping in
            newcd['__example__'] = ''

    @staticmethod
    def load_config_dir(dirpath, filenames, configs_dict, defaults_dict):
        """
        Populate configs_dict with ConfigDict() for sections found in filenames

        :param dirpath: Path to directory of ``ini`` files to load
        :param filenames: List of filenames in directory.
        :param configs_dict: Destination dict-like to store result
        :param defaults_dict: Dict-like containing all default option/values.
        """
        for filename in filenames:
            if CONTROLFILE in filename:
                continue
            fullpath = os.path.join(dirpath, filename)
            if filename.startswith('.') or not filename.endswith('.ini'):
                continue
            config_file = open(fullpath, 'r')
            # Temp use sections variable for reading sections list
            scp = SafeConfigParser()
            scp.readfp(config_file)
            sections = scp.sections()
            for section in sections:
                # First call to defaults_dict will cache result
                newcd = ConfigDict(section, defaults_dict)
                # Will seek(0), incorporate defaults & overwrite any dupes.
                newcd.read(config_file)
                if section not in configs_dict:
                    configs_dict[section] = newcd
                    continue  # all defaults, no processing of __example__
                # Remove __example__ options where newcd option value
                # differs from existing (default) value in configs_dict.
                Config.load_config_sec(scp, newcd, section,
                                       configs_dict, defaults_dict)

    @property
    def configs(self):
        """
        Read-only cached dict of ConfigDict's by section, aggregating all ini's
        """
        if self.__class__.configs_ is None:
            self.__class__.configs_ = {}
            # Overwrite section-by-section from customs after loading defaults
            for dirpath, dirnames, filenames in os.walk(CONFIGDEFAULT):
                del dirnames  # not needed
                self.load_config_dir(dirpath, filenames,
                                     self.__class__.configs_, self.defaults)
            for dirpath, dirnames, filenames in os.walk(CONFIGCUSTOMS):
                del dirnames  # not needed
                self.load_config_dir(dirpath, filenames,
                                     self.__class__.configs_, self.defaults)
        return self.__class__.configs_

    def copy(self):
        """
        Return deep-copy/export as a regular dict containing regular dicts
        """
        the_copy = {}
        # self.configs holds dict of ConfigDict()s
        for sec_key, sec_value in self.configs.items():
            # convert each section from ConfigDict to regular dict.
            sec_copy = {}
            for cfg_key, cfg_value in sec_value.items():
                sec_copy[cfg_key] = cfg_value
            the_copy[sec_key] = sec_copy
        return the_copy


def get_as_list(value, sep=","):
    """
    Return config value as list separated by sep.
    value = "a,b , c, dd"
    return ["a","b","c","dd"]
    """
    return [val.strip() for val in value.split(sep)]


def none_if_empty(dict_like, key_name=None):
    """
    Set empty strings in dict-like to None, if not specific key_name.

    :param dict_like: Instance with dict-like interface to examine
    :param key_name: Optional single key to check, doesn't need to exist.
    """
    if key_name is None:
        keys = dict_like.keys()
    else:
        keys = [key_name]
    for key_name in keys:
        value = dict_like.get(key_name, "")
        if(isinstance(value, (str, unicode)) and
           len(value.strip()) < 1):
            dict_like[key_name] = None
