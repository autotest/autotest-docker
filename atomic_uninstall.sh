#!/bin/sh

echo -e "\n\nUninstalling Atomic Docker Autotest"

if [ -z "${HOST}" ] || [ -z "${CONFDIR}" ] || [ -z "${LOGDIR}" ] || [ -z "${DATADIR}" ] || [ -z "${NAME}" ]
then
    echo "This script is intended to be run from 'atomic install'"
    exit 1
fi

if ! [ -e "${HOST}${CONFDIR}/${NAME}/defaults.ini" ] || ! [ -e "${HOST}${CONFDIR}/${NAME}/control.ini" ]
then
    echo "Not installed."
    exit 1
fi

echo -e "\n\nRenaming default configuration"
mv -v "${HOST}${CONFDIR}/${NAME}/defaults.ini" "${HOST}${CONFDIR}/${NAME}/defaults.ini.old"
mv -v "${HOST}${CONFDIR}/${NAME}/control.ini" "${HOST}${CONFDIR}/${NAME}/control.ini.old"

echo -e "Done."
