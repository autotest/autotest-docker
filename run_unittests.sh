#!/bin/bash

echo ""
echo ""
for unittest in dockertest/*_unittests.py
do
    ${unittest} --failfast --quiet --buffer &
done
wait %- &> /dev/null
RET=$?
while [ "$RET" -ne "127" ]
do
    sleep "0.1s"
    wait %- &> /dev/null
    RET=$?

    if [ $RET -ne 0 -a $RET -ne 127 ]; then exit $RET; fi
done

if [ -n "$AUTOTEST_PATH" ]
then
    export PYTHONPATH=$(dirname $AUTOTEST_PATH)
else
    python -c 'import autotest'
    if [ "$?" -ne "0" ]
    then
        echo "ERROR: autotest module won't load or"\
             "AUTOTEST_PATH env. var. is not set"
        exit 1
    fi
fi

# Unit tests for subtests.
# FIXME: find a way to have nosetests recurse, or move the tests into
#        a directory structure that nose can handle.
for unittest in $(find subtests -name 'test_*.py'); do
    echo $unittest
    nosetests -v $unittest || exit 1
done

echo ""
echo ""
