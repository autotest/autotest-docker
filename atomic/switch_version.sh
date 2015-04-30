#!/bin/sh

if [ "$#" -lt "2" ]
then
    echo "Usage $(basename $0): AUTOTEST_PATH VERSION"
    exit 1
fi

AUTOTEST_PATH=$1
VERSION=$2

echo -e "\nSwitching Docker Autotest to version $VERSION"
cd $AUTOTEST_PATH/client/tests/docker

git reset --hard $VERSION &> /dev/null
if [ "$?" -ne 0 ]
then
    echo -e "\nVersion not found, using latest"
fi

cd ${AUTOTEST_PATH}/client
AUTOTEST_VERSION=$(tests/docker/atomic/config_value.py \
                   DEFAULTS autotest_version \
                   tests/docker/config_defaults/defaults.ini \
                   tests/docker/config_custom/defaults.ini)
echo -e "\nSwitching Autotest to version $AUTOTEST_VERSION"
git reset --hard "$AUTOTEST_VERSION"
