#!/bin/bash

export PYTHONPATH=$(dirname $0)

echo ""
echo ""
for unittest in dockertest/*_unittests.py
do
    ${unittest} --failfast --quiet --buffer &
done
wait %- &> /dev/null
RET=$?
while [ $RET -ne 127 ]
do
    if [ $RET -ne 0 ]; then exit $RET; fi

    sleep "0.1s"
    wait %- &> /dev/null
    RET=$?
done

# Tests below need to include autotest modules; make sure we can access them.
if [ -n "$AUTOTEST_PATH" ]
then
    export PYTHONPATH=$(dirname $AUTOTEST_PATH):$PYTHONPATH
else
    python -c 'import autotest'
    if [ "$?" -ne "0" ]
    then
        echo "ERROR: autotest module won't load or " \
             "AUTOTEST_PATH env. var. is not set"
        exit 1
    fi
fi

# Unit tests for subtests. Due to autotest layout, the subtest directories
# aren't importable or discoverable by python itself. We have to do our
# own discovery.
for unittest in $(find . -name 'test_*.py' | sort); do
    echo \$ python $unittest
    python $unittest -v || exit 1
done

echo ""
echo ""
