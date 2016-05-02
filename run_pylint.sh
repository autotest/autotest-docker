#!/bin/bash

# FIXME: Replace this whole goddamn thing with something better

# Optional fast-fail on first error encountered
if [ "$#" -gt "0" ] && [ "$1" == "--FF" ]
then
    FF=1
    shift
    echo "Fast-failing on first error encountered"
else
    FF=0
fi

# Red Hat systems still have W0142, dropped in later upstream versions of pylint
if [ -e "/etc/redhat-release" ]
then
    if grep -iq 'enterprise' '/etc/redhat-release' || \
       grep -iq 'centos' '/etc/redhat-release'
    then
        SPECIALONE=",W0142"
    fi
fi

TMPFILENAME="/tmp/run_pylint_$RANDOM"
PEP8=`which pep8`
# for readability, allow multiple spaces after commas, colons & before '='
PEP8IGNORE='E731,E221,E241'
MSGFMT='(pylint) {msg_id}:{line:3d},{column}: {obj}: {msg}'
# Disable 'line too long' - will be picked up by pep8
# Check "note" (W0511) separately
DISABLEMSG="I0011,R0801,R0904,R0921,R0922,C0301,C0326,W0511${SPECIALONE}"
INIT_HOOK="
AP = os.environ.get('AUTOTEST_PATH', '/usr/local/autotest')
sys.path.append(os.path.abspath(AP + '/..'))
sys.path.append(os.path.abspath('.'))
import autotest
import autotest.common
"
SUBTESTDISABLEMSG="I0011,R0801,R0904,E1101,E1002,R0903,F0401,C0103,C0326,C0111,W0232,C0301,W0511,${SPECIALONE}"
SUBTESTINIT_HOOK="
AP = os.environ.get('AUTOTEST_PATH', '/usr/local/autotest')
sys.path.append(os.path.abspath(AP + '/..'))
sys.path.append(os.path.abspath('.'))
import autotest
import autotest.common
import dockertest
"

# Run from top-level dir
MYDIR=$(dirname "$0")
if [ "$PWD" != "$MYDIR" ]
then
    cd "$MYDIR"
fi

cleanup() {
    rm -f "$TMPFILENAME"
}

trap "cleanup" EXIT

echo "0" > "$TMPFILENAME"

record_return() {
    VALUE=$(head -1 "$TMPFILENAME")
    if [ "$1" -gt "0" ]
    then
        echo "          ^^^^^Problem(s) need fixing^^^^^" > /dev/stderr
        echo
        let "VALUE++"
        echo "$VALUE" > "$TMPFILENAME"
    fi
}

# Run a command, checking exit status.
# If command fails: if called with --FF, exit immediately. Otherwise,
# continue but remember to exit with failure at end of tests.
run_ff() {
    "$@"
    if [ $? -ne 0 ]; then
        if [ $FF -ne 0 ]; then
            exit 1
        fi
        record_return 1
    fi
}

check_dockertest() {
    WHAT="$1"
    echo -e "Checking: ${WHAT} "
    run_ff pylint -rn --init-hook="$INIT_HOOK" \
           --disable="$DISABLEMSG" \
           --max-args=6 \
           --min-public-methods=2\
           --no-docstring-rgx='(__.*__)|(_.*)|(__init__)' \
           --output-format="colorized" \
           --rcfile=/dev/null \
           --msg-template="$MSGFMT" "${WHAT}"
    # Just print FIXME/TODO warnings, don't fail on them.
    pylint -rn --init-hook="$INIT_HOOK" \
               --disable=all \
               --enable=W0511 \
               --output-format="colorized" \
               --rcfile=/dev/null \
               --msg-template="$MSGFMT" "${WHAT}"
    if [ -n "$PEP8" ]
    then
        run_ff $PEP8 --ignore=$PEP8IGNORE "$WHAT"
    fi
}

check_dockertests() {
    echo -e "\n\n======================================= dockertest"
    find dockertest -name '*.py' -a -not -name '*_unittest*.py' | sort | \
    while read LINE; do
        trap "break" INT
        check_dockertest "${LINE}"
    done || exit 1
}

check_subtest() {
    WHAT="$1"
    echo -e "Checking: ${WHAT} "
    run_ff pylint -rn --init-hook="$SUBTESTINIT_HOOK" \
           --disable="$SUBTESTDISABLEMSG" \
           --max-args=8 \
           --max-locals=20 \
           --min-public-methods=1\
           --output-format="colorized" \
           --rcfile=/dev/null \
           --msg-template="$MSGFMT" "${WHAT}"
    # Just print FIXME/TODO warnings, don't fail on them.
    pylint -rn --init-hook="$SUBTESTINIT_HOOK" \
               --disable=all \
               --enable=W0511 \
               --output-format="colorized" \
               --rcfile=/dev/null \
               --msg-template="$MSGFMT" "${WHAT}"
    if [ -n "$PEP8" ]
    then
        run_ff $PEP8 --ignore=$PEP8IGNORE "$WHAT"
    fi
}

check_subtests() {
    for thing in pretests subtests intratests posttests
    do
        trap "break" INT
        echo -e "\n\n======================================= ${thing}"
        find ${thing} -name '*.py' | sort | while read LINE; do
            trap "break" INT
            check_subtest "${LINE}"
        done || exit 1
    done
}

if [ "$#" -eq "0" ]
then
    check_dockertests
    check_subtests
else
    for THING in $@
    do
        if echo "$THING" | grep -q 'dockertest'
        then
            check_dockertest "$THING"
        elif echo "$THING" | grep -q 'tests'
        then
            check_subtest "$THING"
        else
            echo "Ignoring $THING"
        fi
    done
fi

FAULTS=$(head -1 "$TMPFILENAME")

if [ "$FAULTS" -gt "0" ]
then
    echo "Total Faults: $FAULTS"
    exit $FAULTS
else
    exit 0
fi
