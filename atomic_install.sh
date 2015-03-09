#!/bin/sh

echo -e "\nInstalling Atomic Docker Autotest"

if [ -z "${HOST}" ] || [ -z "${CONFDIR}" ] || [ -z "${LOGDIR}" ] || [ -z "${DATADIR}" ] || [ -z "${NAME}" ]
then
    echo -e "\nThis script is intended to be run from 'atomic install'"
    exit 1
fi

if [ -e "${HOST}${CONFDIR}/${NAME}/defaults.ini" ] || [ -e "${HOST}${CONFDIR}/${NAME}/control.ini" ]
then
    echo -e "\nAlready installed, not overwriting."
    exit 1
fi

echo -e "\nCreating host directories..."
echo -e "${CONFDIR}${NAME}"
echo -e "${DATADIR}${NAME}"
mkdir -p ${HOST}${CONFDIR}${NAME}
mkdir -p ${HOST}${DATADIR}${NAME}
for subdir in pretests subtests intratests posttests
do
    echo -e "${DATADIR}${NAME}/${subdir}"
    mkdir -p ${HOST}${DATADIR}${NAME}/${subdir}
done
echo -e "${LOGDIR}${NAME}"
mkdir -p ${HOST}${LOGDIR}/${NAME}

echo -e "\nCopying configuration to ${CONFDIR}/${NAME}"
cp ${DOCKER_AUTOTEST_DIR}/config_defaults/control.ini ${HOST}${CONFDIR}/${NAME}
cp ${DOCKER_AUTOTEST_DIR}/config_defaults/defaults.ini ${HOST}${CONFDIR}/${NAME}

for ini in $(grep --files-with-matches -r __example__ \
                  --exclude defaults.ini \
                  ${DOCKER_AUTOTEST_DIR}/config_defaults)
do
    echo "$ini" > /dev/stderr
    cat $ini > /dev/stdout
    echo
done > ${HOST}${CONFDIR}/${NAME}/config.ini

echo -e "\nDone.  Start testing with 'atomic run docker_autotest'"
