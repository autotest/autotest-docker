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

TMPFILENAME="/tmp/run_pylint_$RANDOM"
PEP8=`which pep8`
PEP8IGNORE='E731'
MSGFMT='(pylint) {msg_id}:{line:3d},{column}: {obj}: {msg}'
# Disable 'line too long' - will be picked up by pep8
# Check "note" (W0511) separetly
DISABLEMSG="I0011,R0801,R0904,R0921,R0922,C0301,W0511"
INIT_HOOK="
AP = os.environ.get('AUTOTEST_PATH', '/usr/local/autotest')
sys.path.append(os.path.abspath(AP + '/..'))
sys.path.append(os.path.abspath('.'))
import autotest
import autotest.common
"
SUBTESTDISABLEMSG="I0011,R0801,R0904,E1101,E1002,R0903,F0401,C0103,C0111,W0232,C0301,W0511"
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

check_dockertest() {
    WHAT="$1"
    echo -e "Checking: ${WHAT} "
    pylint -rn --init-hook="$INIT_HOOK" \
           --disable="$DISABLEMSG" \
           --max-args=6 \
           --min-public-methods=2\
           --no-docstring-rgx='(__.*__)|(_.*)|(__init__)' \
           --output-format="colorized" \
           --rcfile=/dev/null \
           --msg-template="$MSGFMT" "${WHAT}"
    RET="$?"
    if [ "$RET" -ne "0" ] && [ "$FF" -eq "1" ]
    then
        record_return 1
        return $RET
    elif [ "$RET" -ne "0" ]
    then
        record_return 1
    else
        # Just print FIXME/TODO warnings, don't fail on them.
        pylint -rn --init-hook="$INIT_HOOK" \
               --disable=all \
               --enable=W0511 \
               --output-format="colorized" \
               --rcfile=/dev/null \
               --msg-template="$MSGFMT" "${WHAT}"
    fi
    if [ -n "$PEP8" ]
    then
        $PEP8 --ignore=$PEP8IGNORE "$WHAT"
        RET="$?"
        if [ "$RET" -ne "0" ] && [ "$FF" -eq "1" ]
        then
            record_return 1
            return $RET
        elif [ "$RET" -ne "0" ]
        then
            record_return 1
        fi
    fi
}

check_dockertests() {
    echo -e "\n\n======================================= dockertest"
    find dockertest -name '*.py' -a -not -name '*_unittest*.py' | \
    while read LINE; do
        trap "break" INT
        check_dockertest "${LINE}"
        RET="$?"
        if [ "$RET" -ne "0" ] && [ "$FF" -eq "1" ]
        then
            return $RET
        fi
    done
}

check_subtest() {
    WHAT="$1"
    echo -e "Checking: ${WHAT} "
    pylint -rn --init-hook="$SUBTESTINIT_HOOK" \
           --disable="$SUBTESTDISABLEMSG" \
           --max-args=8 \
           --max-locals=20 \
           --min-public-methods=1\
           --output-format="colorized" \
           --rcfile=/dev/null \
           --msg-template="$MSGFMT" "${WHAT}"
    RET="$?"
    if [ "$RET" -ne "0" ] && [ "$FF" -eq "1" ]
    then
        record_return 1
        return $RET
    elif [ "$RET" -ne "0" ]
    then
        record_return 1
    else
        # Just print FIXME/TODO warnings, don't fail on them.
        pylint -rn --init-hook="$SUBTESTINIT_HOOK" \
               --disable=all \
               --enable=W0511 \
               --output-format="colorized" \
               --rcfile=/dev/null \
               --msg-template="$MSGFMT" "${WHAT}"
    fi
    if [ -n "$PEP8" ]
    then
        $PEP8 --ignore=$PEP8IGNORE "$WHAT"
        RET="$?"
        if [ "$RET" -ne "0" ] && [ "$FF" -eq "1" ]
        then
            record_return 1
            return $RET
        elif [ "$RET" -ne "0" ]
        then
            record_return 1
        fi
    fi
}

check_subtests() {
    for thing in pretests subtests intratests posttests
    do
        trap "break" INT
        echo -e "\n\n======================================= ${thing}"
        find ${thing} -name '*.py' | while read LINE; do
            trap "break" INT
            check_subtest "${LINE}"
            RET="$?"
            if [ "$RET" -ne "0" ] && [ "$FF" -eq "1" ]
            then
                return $RET
            fi
        done
    done
}

if [ "$#" -eq "0" ]
then
    check_dockertests
    [ "$?" -eq "0" ] || exit 1
    check_subtests
    [ "$?" -eq "0" ] || exit 1
else
    for THING in $@
    do
        if echo "$THING" | grep -q 'dockertest'
        then
            check_dockertest "$THING"
            [ "$?" -eq "0" ] || exit 1
        elif echo "$THING" | grep -q 'tests'
        then
            check_subtest "$THING"
            [ "$?" -eq "0" ] || exit 1
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
