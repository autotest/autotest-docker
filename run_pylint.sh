#!/bin/bash

MSGFMT='{msg_id}:{line:3d},{column}: {obj}: {msg}'
DISABLEMSG="I0011,R0801,R0904,R0921,R0922"
INIT_HOOK="
AP = os.environ.get('AUTOTEST_PATH', '/usr/local/autotest')
sys.path.append(os.path.abspath(AP + '/..'))
sys.path.append(os.path.abspath('.'))
import autotest
import autotest.common
"

# Run from top-level dir
MYDIR=$(dirname "$0")
if [ "$PWD" != "$MYDIR" ]
then
    cd "$MYDIR"
fi

trap "exit" INT

echo -e "\n\n======================================= dockertest"
find dockertest -name '*.py' -a -not -name '*_unittest*.py' | \
while read LINE; do
    echo -e "Dockertest module: ${LINE} "
    pylint -rn --init-hook="$INIT_HOOK" \
           --disable="$DISABLEMSG" \
           --max-args=6 \
           --no-docstring-rgx='(__.*__)|(_.*)|(__init__)' \
           --output-format="colorized" \
           --rcfile=/dev/null \
           --msg-template="$MSGFMT" "${LINE}"
    if [ "$?" -ne "0" ]
    then
        echo
    fi
done

echo -e "\n\n======================================= subtests"
SUBTESTDISABLEMSG="I0011,R0801,R0904,E1101,E1002,R0903,F0401,C0103,C0111,W0232,W0142"
INIT_HOOK="
AP = os.environ.get('AUTOTEST_PATH', '/usr/local/autotest')
sys.path.append(os.path.abspath(AP + '/..'))
sys.path.append(os.path.abspath('.'))
import autotest
import autotest.common
import dockertest
"
find subtests -name '*.py' | while read LINE; do
    echo -e "Subtest module: ${LINE} "
    pylint -rn --init-hook="$INIT_HOOK" \
           --disable="$SUBTESTDISABLEMSG" \
           --max-args=8 \
           --max-locals=20 \
           --output-format="colorized" \
           --rcfile=/dev/null \
           --msg-template="$MSGFMT" "${LINE}"
    if [ "$?" -ne "0" ]
    then
        echo
    fi
done
