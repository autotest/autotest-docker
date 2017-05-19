#!/bin/bash
#
# Helper script for the deferred-deletion test. We need this to be outside
# of python because (1) we need to nsenter the docker daemon mount namespace,
# and (2) autotest runs multithreaded so setns() will not work. So our
# autotest invokes us via nsenter.
#
# We are given the name of a running docker container. From that we:
#
#  1) Find out its local mount point. cd into it.
#  2) Run 'docker info' to get the Deferred Deletion count. Save it.
#  3) Stop the container and wait for it to be gone.
#  4) Run 'docker info' and get new Deferred Deletion count. It should be
#     one more than what we got in step (2).
#  5) cd outside of the container's mount point.
#  6) Wait up to 30 seconds, running 'docker info' frequently to check
#     Deferred Deletion count. If it goes back to the value in step (2), pass.
#
deferred_count() {
    docker info | grep 'Deferred Deleted Device Count:' | awk -F: '{print $2}'
}

wait_for_container_to_die() {
    wait_until=$(expr $SECONDS + 5)

    while [ $SECONDS -le $wait_until ]; do
        found=$(docker ps -a --quiet --filter=name=$c_name)
        if [ -z "$found" ]; then
            return
        fi
        sleep 0.1
    done

    echo "FATAL: Container failed to exit properly"
    exit 1
}


c_name=${1?FATAL: Missing CONTAINER_NAME argument}
trigger_file=${2?FATAL: Missing TRIGGER_FILE argument}

# Ask docker for the devmapper name of the container filesystem...
dname=$(docker inspect --format '{{.GraphDriver.Data.DeviceName}}' $c_name)

# ...then from that find the path to the local mount.
mountpoint=$(findmnt --noheadings --output TARGET --source /dev/mapper/$dname)
if [ -z "$mountpoint" ]; then
    echo "FATAL: No mount point for /dev/mapper/$dname" >&2
    exit 1
fi

cd "$mountpoint/rootfs" || exit 1

# Container is running; count on a test system should always be 0, but
# don't enforce that.
starting_count=$(deferred_count)
if [ $starting_count -ne 0 ]; then
    echo "WARNING: Deferred-Delete count from 'docker info' is $starting_count (I expected 0). This may mean your system has still-undeleted containers."
fi

# The container is spinning, it will stop as soon as this file is removed.
rm -f $trigger_file
wait_for_container_to_die

# Check count again, it should be 1
now_count=$(deferred_count)
expected_count=$(expr $starting_count + 1)
if [ $now_count -ne $expected_count ]; then
    echo "FATAL: deferred count is $now_count; I expected $expected_count"
    exit 1
fi

# cd out of the container, then wait for count to go back down
cd /

wait_until=$(expr $SECONDS + 30)
while [ $SECONDS -le $wait_until ]; do
    now_count=$(deferred_count)
    if [ $now_count -eq $starting_count ]; then
        exit 0
    fi
    sleep 0.1
done

echo "FATAL: deferred count never went back to $starting_count"
exit 1
