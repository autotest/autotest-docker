"""
API compatibility: on 2016-04-29 output.py got split up into a
package with four smaller, more maintainable submodules. This init
allows existing clients to continue importing as a single unit.
"""

# ARGH. Without this, 'import xceptions' in a submodule fails because
# dockertest isn't in the search path.
from os.path import dirname
__path__ += [dirname(__path__[0])]

# pylint: disable=W0401
from . dockertime import *
from . dockerversion import *
from . texttable import *
from . validate import *
