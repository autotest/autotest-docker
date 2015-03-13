#!/bin/sh

echo -e "\nUninstalling Atomic Docker Autotest"

if [ -z "${HOST}" ] || [ -z "${NAME}" ]
then
    echo "This script is intended to be run from 'atomic install'"
    exit 1
fi

if ! [ -e "${HOST}/etc/${NAME}/defaults.ini" ] || ! [ -e "${HOST}/etc/${NAME}/config.ini" ]
then
    echo "Not installed."
    exit 1
fi

echo -e "\nRenaming default configuration"
mv -v "${HOST}/etc/${NAME}/defaults.ini" "${HOST}/etc/${NAME}/defaults.ini.old"
mv -v "${HOST}/etc/${NAME}/control.ini" "${HOST}/etc/${NAME}/control.ini.old"

echo -e "Done."
