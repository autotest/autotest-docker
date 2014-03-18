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
echo ""
echo ""
