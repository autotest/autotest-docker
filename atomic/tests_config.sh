#!/bin/sh

if [ "$#" -lt "1" ]
then
    echo "Usage $(basename $0): AUTOTEST_PATH"
    exit 1
fi

AUTOTEST_PATH=$1

echo -e "\nSetting up Docker Autotest Test Configuration..."
cd $AUTOTEST_PATH/client/tests/docker

if ! [ -f "config_custom/tests.ini" ]
then
    echo "Creating 'config_custom/tests.ini'"
    # All config files with an __example__ key are recommended for customization
    for ini in $(grep --files-with-matches -r __example__ \
                 --exclude defaults.ini \
                 --exclude subtests/example.ini \
                 config_defaults)
    do
        cat $ini
        echo
    done >> config_custom/tests.ini
    if [ "$?" -ne 0 ]; then exit 1; fi
fi
