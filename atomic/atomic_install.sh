#!/bin/sh

DEST="${HOST}${AUTOTEST_PATH}"
SRC="/usr/local/autotest/* /usr/local/autotest/.??*"

echo -e "\nInstalling to $DEST"

if [ -z "$HOST" ]
then
    echo -e "\nAborting. HOST env. var is not set"
    exit 4
fi

if [ -f "$DEST/client/autotest-local" ]
then
    echo -e "\nWARNING: Existing $DEST renamed to ${DEST}.backup"
    rm -rf "${DEST}.backup"
    mv "$DEST" "${DEST}.backup"
fi

mkdir "${DEST}"
if [ "$?" -ne 0 ]; then exit 1; fi

echo -e "\nTransfering runtime to host..."
cp -a ${SRC} ${DEST}
if [ "$?" -ne 0 ]; then exit 1; fi

# Reset to latest version or use tag
if echo -n "${IMAGE}" | grep -q ':'
then
    ATD_IMAGE=$(echo "${IMAGE}" | cut -d: -f 1)
    ATD_TAG=$(echo "${IMAGE}" | cut -d: -f2)
else  # does not contain a tag, force latest
    ATD_IMAGE=${IMAGE}
    ATD_TAG="latest"
fi

if [ -n "$SWITCH_VERSION" ]
then
    ${AUTOTEST_PATH}/client/tests/docker/atomic/switch_version.sh $DEST $ATD_TAG
    if [ "$?" -ne 0 ]; then exit 1; fi
fi

if [ -n "$TESTS_CONFIG" ]
then
    ${AUTOTEST_PATH}/client/tests/docker/atomic/tests_config.sh $DEST
    if [ "$?" -ne 0 ]; then exit 1; fi
fi

${AUTOTEST_PATH}/client/tests/docker/atomic/defaults_config.sh $DEST $ATD_IMAGE $ATD_TAG "$PROTECT_IMAGES"
if [ "$?" -ne 0 ]; then exit 1; fi

${AUTOTEST_PATH}/client/tests/docker/atomic/control_config.sh $DEST
if [ "$?" -ne 0 ]; then exit 1; fi

echo -e "\nExecute tests with: atomic run ${IMAGE}"
echo -e "or"
echo -e "${AUTOTEST_PATH}/client/autotest-local run docker"
echo -e "or"
echo -e "${AUTOTEST_PATH}/client/autotest-local run docker --args=names,of,tests,to,run"
