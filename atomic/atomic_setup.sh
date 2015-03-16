#!/bin/sh

echo -e "\nInstalling ${NAME}..."

if [ -n "$VERBOSE" ]
then
    QUIET=""
    OUTPUT="/dev/stderr"
else
    QUIET="--quiet"
    OUTPUT="/dev/null"
fi

TMPNAME="${RANDOM}${RANDOM}${IMAGE}"
TMPDIR="${HOST}/var/tmp/build${TMPNAME}${IMAGE}"

cleanup() {
    echo -e "\nCleaning up..."

    cd /
    rm -rf "${TMPDIR}" ${OUTPUT}
    ${HOST}/usr/bin/docker rm --force ${TMPNAME} &> ${OUTPUT}
    ${HOST}/usr/bin/docker rmi --force ${TMPNAME} &> ${OUTPUT}

    echo -e "\nDone. Start testing with: atomic run ${IMAGE}"
}

mkdir -p "${TMPDIR}"
if [ "$?" -ne 0 ]; then exit 1; fi

trap cleanup EXIT

# Avoid uploading random crap as context to daemon
cd "${TMPDIR}"
if [ "$?" -ne 0 ]; then exit 1; fi

RUNSCRIPT="${HOST_ROOT}/${NAME}${DOCKER_AUTOTEST_PATH}/atomic/atomic_run.sh"
if [ -f "$HOST$RUNSCRIPT" ]
then
    echo -e "\nExisting installation found, not overwriting..."
else
    # Docker autotest exercises docker, so cannot be run under docker.
    echo -e "\nCreating ${HOST_ROOT}/${NAME}" &> ${OUTPUT}
    mkdir -p ${HOST}${HOST_ROOT}/${NAME}
    if [ "$?" -ne 0 ]; then exit 1; fi

    echo -e "\nTransfering image contents to host's ${HOST_ROOT}/${NAME}..."
    # Need container to extract filesystem
    ${HOST}/usr/bin/docker run --name ${TMPNAME} ${IMAGE} true &> ${OUTPUT}
    if [ "$?" -ne 0 ]; then exit 1; fi
    ${HOST}/usr/bin/docker export ${TMPNAME} | \
        tar -C ${HOST}${HOST_ROOT}/${NAME} -xf - &> ${OUTPUT}
    if [ "$?" -ne 0 ]; then exit 1; fi
    ${HOST}/usr/bin/docker rm --force ${TMPNAME} &> ${OUTPUT}
    if [ "$?" -ne 0 ]; then exit 1; fi
fi

# Check if install/setup was already run
if ! ${HOST}/usr/bin/docker inspect --format '{{.Config.Labels.RUN}}' ${IMAGE} | \
     grep -q '/usr/bin/docker'
then
    echo -e "\nBuilding runtime onto base image..." &> ${OUTPUT}
    # Add a layer ontop of original build image for starting docker autotest
    OLDIID=$(${HOST}/usr/bin/docker inspect --format "{{.Id}}" ${IMAGE} | cut -c 1-12)
    if [ "$?" -ne 0 ]; then exit 1; fi
    ${HOST}/usr/bin/docker build ${QUIET} -t ${IMAGE} - <<EOF
FROM ${OLDIID}
LABEL RUN="${RUNSCRIPT} ${NAME} ${AUTOTEST_PATH} ${DOCKER_BIN_PATH}"
LABEL UNINSTALL="rm -rf ${HOST_ROOT}/${NAME}"
EOF
    if [ "$?" -ne 0 ]; then exit 1; fi
else
    echo -e "\nExisting runtime image detected, not rebuilding."
fi

# Setup basic configuration if doesn't exist
CONFIGCUSTOM="${HOST}${HOST_ROOT}/${NAME}${DOCKER_AUTOTEST_PATH}/config_custom"
CONFIGDEFAULTS="${HOST}${HOST_ROOT}/${NAME}${DOCKER_AUTOTEST_PATH}/config_defaults"
# Build basic configuration if doesn't exist
if [ -f "${CONFIGCUSTOM}/defaults.ini" ] || [ -f "${CONFIGCUSTOM}/control.ini" ]
then
    echo -e "\nNot overwriting existing configuration."
else
    echo -e "\nCreating configuration in ${HOST_ROOT}/${NAME}${DOCKER_AUTOTEST_PATH}/config_custom"
    cp ${CONFIGDEFAULTS}/control.ini ${CONFIGCUSTOM}
    cp ${CONFIGDEFAULTS}/defaults.ini ${CONFIGCUSTOM}
    for ini in $(grep --files-with-matches -r __example__ \
                 --exclude defaults.ini \
                 --exclude subtests/example.ini ${CONFIGDEFAULTS})
    do
        cat $ini
        echo
    done >> ${CONFIGCUSTOM}/test_config.ini
fi
