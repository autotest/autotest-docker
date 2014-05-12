This subdirectory is searched first for ``defaults.ini``.
If found, it's options will become the defaults for all other
configuration sections.  In this case, the
``config_defaults/defaults.ini`` file will be completely ignored.

Next, all regular configuration files in the ``config_defaults``
subdirectory are loaded and parsed.

Finally, all regular configuration files in this subdirectory
are parsed.  If any configuration sections clash, the sections
loaded from files in **this** (``config_custom``) directory will
override any previously loaded.

Except for ``defaults.init``, the parsing order within this
subdirectory (as in ``config_defaults``) is completely undefined.
If multiple files contain duplicate sections with differing options,
the active set will be undefined.
