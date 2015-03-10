#!/bin/sh

cd ${DOCKER_AUTOTEST_PATH}
git remote update
if [ "$?" -ne 0 ]; then exit 1; fi
git reset --hard origin/${DOCKER_AUTOTEST_BRANCH}
if [ "$?" -ne 0 ]; then exit 1; fi

cd ${AUTOTEST_PATH}/client
git reset --hard $(${DOCKER_AUTOTEST_PATH}/atomic/config_value.py \
                       DEFAULTS autotest_version \
                       ${DOCKER_AUTOTEST_PATH}/config_defaults/defaults.ini)
if [ "$?" -ne 0 ]; then exit 1; fi

# This makes testing the install script easier
exec ${DOCKER_AUTOTEST_PATH}/atomic/atomic_setup.sh
