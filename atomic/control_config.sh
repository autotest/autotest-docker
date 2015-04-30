#!/bin/sh

if [ "$#" -lt "1" ]
then
    echo "Usage $(basename $0): AUTOTEST_PATH"
    exit 1
fi

AUTOTEST_PATH=$1

echo -e "\nSetting up Docker Autotest Control Configuration..."
cd $AUTOTEST_PATH/client/tests/docker

if ! [ -f "config_custom/control.ini" ]
then
    cp config_defaults/control.ini config_custom/
    if [ "$?" -ne 0 ]; then exit 1; fi
fi
