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
if [ -e "$HOST$RUNSCRIPT" ]
then
    echo -e "\n Existing host $HOST$RUNSCRIPT found, not overwriting..."
else
    # Docker autotest exercises docker, so cannot be run under docker.
    echo -e "\nTransfering image contents to host's ${HOST_ROOT}/${NAME}..."

    mkdir -vp ${HOST}${HOST_ROOT}/${NAME} &> ${OUTPUT}
    if [ "$?" -ne 0 ]; then exit 1; fi

    # Need container to extract filesystem
    ${HOST}/usr/bin/docker run --name ${TMPNAME} ${IMAGE} true &> ${OUTPUT}
    if [ "$?" -ne 0 ]; then exit 1; fi
    ${HOST}/usr/bin/docker export ${TMPNAME} | \
        tar -C ${HOST}${HOST_ROOT}/${NAME} -xf - &> ${OUTPUT}
    if [ "$?" -ne 0 ]; then exit 1; fi
    ${HOST}/usr/bin/docker rm --force ${TMPNAME} &> ${OUTPUT}
    if [ "$?" -ne 0 ]; then exit 1; fi
fi

# Add a layer ontop of original build image for starting docker autotest
OLDIID=$(${HOST}/usr/bin/docker inspect --format "{{.Id}}" ${IMAGE} | cut -c 1-12)
if [ "$?" -ne 0 ]; then exit 1; fi
${HOST}/usr/bin/docker build ${QUIET} -t ${IMAGE} - <<EOF
FROM ${OLDIID}
LABEL INSTALL=""
LABEL RUN="${RUNSCRIPT} ${NAME} ${AUTOTEST_PATH} ${DOCKER_BIN_PATH}"
LABEL UNINSTALL="rm -rf ${HOST_ROOT}/${NAME}"
EOF
if [ "$?" -ne 0 ]; then exit 1; fi

# Tag former first stage w/ name pointing to second-stage ID
#NEWIID=$(${HOST}/usr/bin/docker inspect --format "{{.Id}}" ${IMAGE} | cut -c 1-12)
#${HOST}/usr/bin/docker tag ${OLDIID} ${NAME}:${NEWIID}
#if [ "$?" -ne 0 ]; then exit 1; fi
