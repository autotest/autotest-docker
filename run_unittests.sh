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
done

if [ -n "$AUTOTEST_PATH" ]
then
    export PYTHONPATH=$(dirname $AUTOTEST_PATH)
fi

# Unit tests for subtests.
# FIXME: find a way to have nosetests recurse, or move the tests into
#        a directory structure that nose can handle.
for unittest in $(find subtests -name 'test_*.py'); do
    nosetests -v $unittest
done

echo ""
echo ""
