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
    export PYTHONPATH=$(dirname $AUTOTEST_PATH):$(dirname $0)
else
    python -c 'import autotest'
    if [ "$?" -ne "0" ]
    then
        echo "ERROR: autotest module won't load or"\
             "AUTOTEST_PATH env. var. is not set"
        exit 1
    fi
    export PYTHONPATH=$(dirname $0)
fi

# Unit tests for subtests. Due to autotest layout, the subtest directories
# aren't importable or discoverable by python itself. We have to do our
# own discovery.
for unittest in $(find subtests -name 'test_*.py'); do
    echo $unittest
    python $unittest -v || exit 1
done

echo ""
echo ""
