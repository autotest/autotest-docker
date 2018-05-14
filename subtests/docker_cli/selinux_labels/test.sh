#!/bin/bash
#
# Test SELinux labels of running docker processes and of containers
#

if [ $# -ne 1 ]; then
    echo "Usage: $0 IMAGE-NAME"
    exit 1
fi
image="$1"

# Exit status. Default 0 (success), but set to 1 on any subtest failure
rc=0

if [ ! -e /usr/sbin/selinuxenabled ] || ! /usr/sbin/selinuxenabled; then
    echo "FAIL selinux is disabled"
    exit 1
fi

# Main code. Run a command whose output is expected to be a single line,
# and the first field is a security context (user:role:type:level); verify
# that command generates exactly one line of output; extract the <type>
# and <level> fields; and check against a list of one or more expected
# values. Assume that there's no overlap between valid types & ranges.
check_label() {
    local name="$1"; shift
    local command="$1"; shift

    # Should return a string like "foo_u:foo_r:foo_t:s0..."
    result=$(eval "$command")
    if [ -z "$result" ]; then
        echo "FAILED $name: no output from '$command'"
        rc=1
        return
    fi
    nlines=$(echo "$result" | wc -l)
    if [ $nlines -gt 1 ]; then
        echo "FAILED $name: too much output from '$command'"
        rc=1
        return
    fi

    # e.g. system_u:system_r:docker_t:s0:c1,c2 -> "docker_t" & "s0:c1,c2"
    type=$(echo "$result" | cut -d: -f3)
    range=$(echo "$result" | cut -d: -f4,5)

    for expect in "$@"; do
        if [ "$type" = "$expect" -o "$range" = "$expect" ]; then
            echo "PASS $name = $expect"
            return
        fi
    done

    echo "FAILED $name: expected $@, got $type:$range"
    rc=1
}

# Actual checks
check_label "docker-containerd" \
            "ps axZ | grep docker-containerd | grep -v grep" \
            "container_runtime_t" "docker_t"

check_label "dockerd" \
            "ps axZ | grep dockerd | grep -v grep" \
            "container_runtime_t" "docker_t"

check_label "confined container" \
            "docker run --rm $image cat /proc/self/attr/current" \
            "container_t" "svirt_lxc_net_t"

check_label "container with label=disable" \
            "docker run --rm --security-opt label=disable $image cat /proc/self/attr/current" \
            "spc_t"

check_label "container with overriden type" \
            "docker run --rm --security-opt label=type:svirt_qemu_net_t $image cat /proc/self/attr/current" \
            "svirt_qemu_net_t"

check_label "privileged container" \
            "docker run --rm --privileged --userns=host $image cat /proc/self/attr/current" \
            "spc_t"

check_label "confined container: root dir" \
            "docker run --rm $image ls -dZ /" \
            "container_file_t" "svirt_sandbox_file_t"

check_label "container with overridden range" \
            "docker run --rm --security-opt label=level:s0:c1,c2 $image cat /proc/self/attr/current" \
            "s0:c1,c2"

exit $rc
