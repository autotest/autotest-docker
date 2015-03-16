#!/bin/sh

HRN="${HOST_ROOT}/$(echo -n "$IMAGE" | tr ':' '-')"
CONFIGCUSTOM="${HOST}${HRN}${DOCKER_AUTOTEST_PATH}/config_custom"
CONFIGDEFAULTS="${HOST}${HRN}${DOCKER_AUTOTEST_PATH}/config_defaults"
RUNSCRIPT="${HRN}${DOCKER_AUTOTEST_PATH}/atomic/atomic_run.sh"
TMPNAME="${RANDOM}${RANDOM}${NAME}"
TMPDIR="${HOST}/var/tmp/build${TMPNAME}"

if [ -f "$HOST$RUNSCRIPT" ]
then
    echo -e "\nAborting. Existing installation found on host in ${HRN}/"
    exit 2
fi

if [ -n "$VERBOSE" ]
then
    QUIET=""
    OUTPUT="/dev/stderr"
else
    QUIET="--quiet"
    OUTPUT="/dev/null"
fi

# Docker autotest exercises docker, so cannot be run under docker.
echo -e "\nCreating ${HRN}/" &> ${OUTPUT}
mkdir ${HOST}${HRN}
if [ "$?" -ne 0 ]; then exit 1; fi

cleanup() {
    echo -e "\nCleaning up..."
    cd /
    rm -rf "${TMPDIR}" &> ${OUTPUT}
    # Don't rely on test docker binary to clean up
    chroot ${HOST} /usr/bin/docker rm --force ${TMPNAME} &> /dev/null
}

trap cleanup EXIT

# Avoid uploading random crap as context to daemon
mkdir -p "${TMPDIR}" && cd "${TMPDIR}"
if [ "$?" -ne 0 ]; then exit 1; fi

# Check if install/setup was already run
if chroot ${HOST} /usr/bin/docker inspect --format '{{.Config.Labels.RUN}}' ${IMAGE} | \
                                                        grep -q "${DOCKER_BIN_PATH}"
then
    echo -e "\nExisting run time image detected, not rebuilding."
else
    echo -e "\nBuilding run time image..." &> ${OUTPUT}
    # Add a layer ontop of original build image with all the details
    OLDIID=$(chroot ${HOST} /usr/bin/docker inspect --format "{{.Id}}" ${IMAGE} | cut -c 1-12)
    if [ "$?" -ne 0 ]; then exit 1; fi
    # Don't rely on test docker binary to build, use host
    chroot ${HOST} /usr/bin/docker build ${QUIET} -t ${IMAGE} - <<EOF
FROM ${OLDIID}
LABEL RUN="${RUNSCRIPT} ${IMAGE} ${AUTOTEST_PATH} ${DOCKER_BIN_PATH}"
LABEL UNINSTALL="rm -rf ${HRN}"
EOF
    if [ "$?" -ne 0 ]; then exit 1; fi
fi

echo -e "\nTransfering image contents to host's ${HRN}/..."
# Need container to extract filesystem
chroot ${HOST} /usr/bin/docker run --name ${TMPNAME} ${IMAGE} true &> ${OUTPUT}
if [ "$?" -ne 0 ]; then exit 1; fi
chroot ${HOST} /bin/sh -c "/usr/bin/docker export ${TMPNAME} | \
                           tar -C ${HRN} -xf -" &> ${OUTPUT}
if [ "$?" -ne 0 ]; then exit 1; fi

echo -e "\nCreating symlink from:\n${HRN}${DOCKER_AUTOTEST_PATH}\nto:\n${HRN}/docker\n"
cd ${HOST}${HRN}
ln -s $(echo "${DOCKER_AUTOTEST_PATH}" | cut -c 2-) "docker"

echo -e "\nSetting up Docker Autotest Configuration..."
# Setup basic configuration if doesn't exist
if [ -f "${CONFIGCUSTOM}/control.ini" ]
then
    echo -e "\nNot overwriting existing control.ini"
else
    echo -e "\nCopying control config to ${HRN}/docker/config_custom/control.ini"
    cp ${CONFIGDEFAULTS}/control.ini ${CONFIGCUSTOM}
    if [ "$?" -ne 0 ]; then exit 1; fi
fi

if [ -f "${CONFIGCUSTOM}/defaults.ini" ]
then
    echo -e "\nNot overwriting existing defaults.ini"
else
    echo -e "\nBuilding env. config ${HRN}/docker/config_custom/defaults.ini"
    # Test image name was not known until this script
    sed -re "
s|docker_path =.*|docker_path = ${DOCKER_BIN_PATH}|
s|docker_repo_name =.*|docker_repo_name = ${IMAGE}|
s|docker_registry_host =.*|docker_registry_host =|
s|docker_registry_user =.*|docker_registry_user =|
    " ${CONFIGDEFAULTS}/defaults.ini > ${CONFIGCUSTOM}/defaults.ini
    if [ "$?" -ne 0 ]; then exit 1; fi
fi

if [ -f "${CONFIGCUSTOM}/tests.ini" ]
then
    echo -e "\nNot overwriting existing tests.ini"
else
    echo -e "\nBuilding ${HRN}/docker/config_custom/tests.ini"
    for ini in $(grep --files-with-matches -r __example__ \
                 --exclude defaults.ini \
                 --exclude subtests/example.ini \
                 --exclude garbage_check.ini \
                 ${CONFIGDEFAULTS})
    do
        cat $ini
        echo
    done >> ${CONFIGCUSTOM}/tests.ini
    if [ "$?" -ne 0 ]; then exit 1; fi
fi

if [ -f "${CONFIGCUSTOM}/intratests.ini" ]
then
    echo -e "\nNot overwriting existing intratests.ini"
else
    echo -e "\nBuilding inttra-test config. ${HRN}/docker/config_custom/intratests.ini"
    sed -re "
s|remove_garbage =.*|remove_garbage = yes|
s|fail_on_unremoved =.*|fail_on_unremoved = yes|
s|\s+ATOMIC_DOCKER_AUTOTEST|           ${IMAGE},${PROTECT_IMAGES}|
s|ignore_cnames =.*|ignore_cnames = ${PROTECT_CONTAINERS}|
    " ${CONFIGDEFAULTS}/intratests.ini > ${CONFIGCUSTOM}/intratests.ini
    if [ "$?" -ne 0 ]; then exit 1; fi
fi

echo -e "\nDone. Start testing with: atomic run ${IMAGE}"
