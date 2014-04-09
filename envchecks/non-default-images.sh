#!/bin/bash

if [ -z "${docker_path}" ]
then
    exit 5
fi

DOCKER_IMAGES=$("${docker_path}" images --all --no-trunc --quiet)
IGNORE_IMAGES=$(echo "${envcheck_ignore_iids}" | tr ',' ' ')

ignore_it() {
    iid="$1"
    for ignore_id in $IGNORE_IMAGES
    do
        if ( echo "$iid" | grep -q "$ignore_id" - )
        then
            echo "Ignoring $ignore_id" > /dev/stdout
            return 0 # good
        fi
    done
    return 1 # bad
}

for iid in $DOCKER_IMAGES
do
    ignore_it "$iid"
    if [ "$?" -ne "0" ]
    then
        DETAIL=$("${docker_path}" images --all --no-trunc | grep "$iid")
        NAME_TAG=$(echo "$DETAIL" | awk '{print $1,$2}')
        echo "Found unexpected image: $NAME_TAG $iid" > /dev/stderr
        exit 3
    fi
done
