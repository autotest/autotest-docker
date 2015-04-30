#!/bin/sh

if [ "$#" -lt "4" ]
then
    echo "Usage $(basename $0): AUTOTEST_PATH ATD_IMAGE ATD_TAG PROTECT_IMAGES"
    exit 1
fi

AUTOTEST_PATH=$1
ATD_IMAGE=$2
ATD_TAG=$3
PROTECT_IMAGES=$4

echo -e "\nSetting up Docker Autotest Defaults Configuration..."
cd $AUTOTEST_PATH/client/tests/docker

if ! [ -f "config_custom/defaults.ini" ]
then
    echo "Creating 'config_custom/defaults.ini'"
    DAEMON_PID=$(cat /run/docker.pid)
    DAEMON_OPTIONS=$(cat /proc/${DAEMON_PID}/cmdline | tr '\000' ',' | cut -d, -f 2-)
    sed -re "
    s|daemon_options =.*|daemon_options = ${DAEMON_OPTIONS}|
    s|docker_repo_name =.*|docker_repo_name = ${ATD_IMAGE}|
    s|docker_repo_tag =.*|docker_repo_tag = ${ATD_TAG}|
    s|docker_registry_host =.*|docker_registry_host =|
    s|docker_registry_user =.*|docker_registry_user =|
    s|^( +)ATOMIC_SUBSTITUTIONS|\1${IMAGE},\n\1${ATD_IMAGE}:${ATD_TAG},\n\1${PROTECT_IMAGES}|
    s|preserve_cnames =.*|preserve_cnames = ${PROTECT_CONTAINERS}|
    " config_defaults/defaults.ini > config_custom/defaults.ini
    if [ "$?" -ne 0 ]; then exit 1; fi
fi
