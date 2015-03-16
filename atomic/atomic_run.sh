#!/bin/bash

# Needed to locate installed location
NAME="$(echo $1 | tr ':' '-')"
shift
AUTOTEST_PATH="$1"
shift
DOCKER_BIN_PATH="$1"
shift
export AUTOTEST_PATH
ROOT="/var/lib/${NAME}"

# Order is important, sort according to target alpha-length
MNTORDER=$(findmnt --evaluate --list --noheadings --nofsroot | cut -d' ' -f 1 | sort)
if [ "$?" -ne 0 ]; then exit 1; fi

# Locate host filesystems to bind for autotest
# produces evaluatable lines with keys: TARGET, SOURCE, FSTYPE, OPTIONS
MNTPAIRS=$(for TARGET in ${MNTORDER}; do findmnt --first-only --pairs ${TARGET}; done)
if [ "$?" -ne 0 ]; then exit 1; fi

# Unmounting always in reverse order
REVORDER=$(for TARGET in ${MNTORDER}; do echo ${TARGET}; done | sort -r)

MOUNTS=""
cleanup() {
    umount ${ROOT}${DOCKER_BIN_PATH} &> /dev/null
    for TARGET in $REVORDER
    do
        if echo "$TARGET" | egrep -q "(/proc)|(/dev)|(/run)|(/sys)"
        then
            umount ${ROOT}${TARGET} &> /dev/null
        fi
    done
}

trap cleanup EXIT INT

echo "${MNTPAIRS}" | while read MNTPAIR
do
    eval ${MNTPAIR}
    if echo "$TARGET" | egrep -q "(/proc)|(/dev)|(/run)|(/sys)"
    then
        #echo "${TARGET} -> ${ROOT}${TARGET}"
        mkdir -p ${ROOT}${TARGET}
        mount --bind ${TARGET} ${ROOT}${TARGET}
        if [ "$?" -ne 0 ]; then exit 1; fi
        MOUNTS="$MOUNTS ${ROOT}${TARGET}"
    fi
    if [ "$?" -ne 0 ]; then exit 1; fi
done
if [ "$?" -ne 0 ]; then exit 1; fi

# Prevented from installing docker, inside of docker so bind-mount it
touch ${ROOT}${DOCKER_BIN_PATH}
mount --bind ${DOCKER_BIN_PATH} ${ROOT}${DOCKER_BIN_PATH}

export PATH="/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin:/root/bin"
export LC_ALL="C"
echo -e "\nAutotest args: $@\n"
/sbin/chroot "${ROOT}" ${AUTOTEST_PATH}/client/autotest-local run docker $@
echo -e "\nAutotest exit: $?\n"
echo -e "\nResults are in: ${ROOT}${AUTOTEST_PATH}/client/results/\n"
