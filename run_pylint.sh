#!/bin/bash

MSGFMT='{msg_id}:{line:3d},{column}: {obj}: {msg}'
BLACKLIST='conf.py'
DISABLEMSG="I0011"
INIT_HOOK="
AP = os.environ.get('AUTOTEST_PATH', '/usr/local/autotest')
sys.path.append(os.path.abspath(AP + '/..'))
print 'Injected into path %s' % sys.path[-1]
sys.path.append(os.path.abspath('.'))
print 'Injected into path %s' % sys.path[-1]
import autotest
import autotest.common
"

# Run from top-level dir
MYDIR=$(dirname "$0")
if [ "$PWD" != "$MYDIR" ]
then
    echo "Switching to top-level directory \'$MYDIR\'"
    cd "$MYDIR"
fi

find -name '*.py' -a -not -name '*_unittest*.py' | xargs \
    pylint -rn --init-hook="$INIT_HOOK" \
           --ignore="$BLACKLIST" \
           --disable="$DISABLEMSG" \
           --output-format="colorized" \
           --rcfile=/dev/null \
           --msg-template="$MSGFMT"
