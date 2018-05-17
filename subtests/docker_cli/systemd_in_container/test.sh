#!/bin/bash
#
# Test systemd in containers
#

if [ $# -ne 1 ]; then
    echo "Usage: $0 IMAGE-NAME"
    exit 1
fi
image="$1"
timeout=10

# Exit status. Default 0 (success), but set to 1 on any subtest failure
rc=0

# Check that when container is run, its output contains the expected
# string(s). With systemd, the container might be running bug systemd
# freezing execution so we cannot really expect docker run to fail.
check_output() {
    local container="$1"; shift
    local name="$1"; shift

    local lrc=0
    for expect in "$@"; do
        echo "Checking for $expect"
        i=0
        while [ $i -lt $timeout ] ; do
            if docker logs "$container" | grep -q "$expect" ; then
                echo "PASS $name = $expect"
                break
            fi
            sleep 1
            i=$(expr $i + 1)
        done
        if [ $i -eq $timeout ] ; then
            echo "FAILED $name, expecting $expect"
            docker logs "$container"
            lrc=1
            rc=1
            break
        fi
    done

    return $lrc
}

# Actual checks

if docker run -d -ti --name systemd$$ $image /usr/sbin/init ; then
        container_id=$( docker ps -q -f name=systemd$$ )
        check_output "systemd$$" \
                     "systemd in container" \
                     "Set hostname to <$container_id>\." \
                     "Started Journal Service"
        docker rm -f systemd$$
else
        echo "FAILED running systemd in $image"
fi

if docker run -d -ti --name systemd$$ --hostname www.example.test $image /usr/sbin/init ; then
        check_output "systemd$$" \
                     "systemd with hostname set" \
                     "Set hostname to <www\.example\.test>"
        docker rm -f systemd$$
else
        echo "FAILED running systemd in $image"
fi

exit $rc
