#!/bin/bash

# Exit non-zero on the first error
set -e

export PYTHONPATH=$(dirname $0):$PYTHONPATH

echo ""
echo ""
for unittest in $(find dockertest -name '*_unittests.py')
do
    ${unittest} --failfast --quiet --buffer
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
    python $unittest -v
done

echo ""
echo ""
