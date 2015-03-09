################################################################################
# Docker Autotest Dockerfile
#
# Recommended build cmd:
#     docker build --tag docker_autotest .
#
# Recommended run cmd:
#     docker run -it -rm --privileged --net=host --ipc=host --pid=host\
#                --name docker_autotest docker_autotest
#
# Notes:
#    The image and container name "docker_autotest" is excluded from testing
#    by default.  It is not recommended to run more than one docker autotest
#    container at the same time.  The name is intended to clash and prevent
#    this
#
# For Custom config, results, & tests, provide volumes for:
#     $CONFIG_CUSTOM_DIR, $CUSTOM_PRETESTS_DIR, $CUSTOM_INTRATESTS_DIR,
#     $CUSTOM_POSTTESTS_DIR, and/or $RESULTS_DIR
################################################################################
FROM stackbrew/centos:7
MAINTAINER cevich@redhat.com
################################################################################
# Configuration Veriables
################################################################################
# Set EPEL_URL to empty-string to disable setting up (default disabled) repo
ENV INSTALL_RPMS="procps findutils bzip2 gdb bridge-utils \
                  docker nfs-utils git glibc-devel \
                  python-sphinx" \
    EPEL_URL="http://linux.mirrors.es.net/fedora-epel/7/x86_64/e/epel-release-7-5.noarch.rpm" \
    EPEL_RPMS="python-bugzilla"
################################################################################
# Dependency installation
################################################################################
RUN yum --disablerepo=*-eus-* --disablerepo=*-htb-* --disablerepo=*-ha-* \
        --disablerepo=*-rt-* --disablerepo=*-lb-* --disablerepo=*-rs-* \
        --disablerepo=*-sap-* --disablerepo=*beta* install -y deltarpm yum-utils && \
    yum-config-manager --disable *-eus-* *-htb-* *-ha-* *-rt-* *-lb-* *-rs-* \
                       *-sap-* *beta* && \
    yum -y update && yum -y install ${INSTALL_RPMS} && \
    "[" -n "${EPEL_URL}" ] && yum install -y ${EPEL_URL} && \
                              yum-config-manager --disable epel &> /dev/null && \
    "[" -n "${EPEL_URL}" ] && [ -n "${EPEL_RPMS}" ] && \
                              yum --enablerepo=epel install -y ${EPEL_RPMS}
################################################################################
# Environment setup
################################################################################
ENV AUTOTEST_PATH="/usr/local/autotest" \
    AUTOTEST_URL="https://github.com/autotest/autotest.git" \
    DOCKER_AUTOTEST_URL="https://github.com/autotest/autotest-docker.git"
ENV RESULTS_DIR=${AUTOTEST_PATH}/client/results \
    DOCKER_AUTOTEST_DIR=${AUTOTEST_PATH}/client/tests/docker
ENV CONFIG_CUSTOM_DIR=${DOCKER_AUTOTEST_DIR}/config_custom \
    CUSTOM_TESTS_DIR=${DOCKER_AUTOTEST_DIR}/subtests/custom \
    PRETESTS_DIR=${DOCKER_AUTOTEST_DIR}/pretests/custom \
    INTRATESTS_DIR=${DOCKER_AUTOTEST_DIR}/intratests/custom \
    POSTTESTS_DIR=${DOCKER_AUTOTEST_DIR}/posttests/custom
################################################################################
# Version-independent test harness installation
################################################################################
# Allows version change through runntime configuration (see below)
RUN git clone --single-branch ${AUTOTEST_URL} ${AUTOTEST_PATH} && \
    git clone --single-branch ${DOCKER_AUTOTEST_URL} ${DOCKER_AUTOTEST_DIR}
ADD https://raw.githubusercontent.com/autotest/autotest-docker/master/config_value.py ${DOCKER_AUTOTEST_DIR}/
# LABEL INSTALL can't use any env. vars inside --entrypoint
ADD https://raw.githubusercontent.com/autotest/autotest-docker/master/atomic_install.sh /root/
ADD https://raw.githubusercontent.com/autotest/autotest-docker/master/atomic_uninstall.sh /root/
################################################################################
# Atomic setup
################################################################################
LABEL INSTALL="/usr/bin/docker run --interactive --tty --rm --privileged --net=host --ipc=host --pid=host --env HOST=/host --env NAME=docker_autotest --env IMAGE=IMAGE --env CONFDIR=/etc/${NAME} --env LOGDIR=/var/log/${NAME} --env DATADIR=/var/lib/${NAME} --volume /:/host --entrypoint '/root/atomic_install.sh' --name docker_autotest docker_autotest"
# FIXME: env. vars don't work with --volume
LABEL RUN="/usr/bin/docker run --interactive --tty --rm --privileged --net=host --ipc=host --pid=host --volume /etc/docker_autotest:/usr/local/autotest/client/tests/docker/config_custom --volume /var/log/docker_autotest:/usr/local/autotest/client/results --volume /var/lib/docker_autotest/pretests:/usr/local/autotest/client/tests/docker/pretests/custom --volume /var/lib/docker_autotest/subtests:/usr/local/autotest/client/tests/docker/subtests/custom --volume /var/lib/docker_autotest/intratests:/usr/local/autotest/client/tests/docker/intratests/custom --volume /var/lib/docker_autotest/posttests:/usr/local/autotest/client/tests/docker/posttests/custom --name docker_autotest docker_autotest"
LABEL UNINSTALL="/usr/bin/docker run --interactive --tty --rm --privileged --net=host --ipc=host --pid=host --env HOST=/host --env NAME=docker_autotest --env IMAGE=IMAGE --env CONFDIR=/etc/${NAME} --env LOGDIR=/var/log/${NAME} --env DATADIR=/var/lib/${NAME} --volume /:/host --entrypoint '/root/atomic_uninstall.sh' --name docker_autotest docker_autotest"
################################################################################
# Runtime Setup
################################################################################
# Content of config_custom/defaults.ini at runtime is unpredictable,
# reset code to configured versions during runtime.  Permits one image
# to be used for multiple test runs against different versions of docker autotest
ENV CFG="${DOCKER_AUTOTEST_DIR}/config_defaults/defaults.ini ${DOCKER_AUTOTEST_DIR}/config_custom/defaults.ini"
ENV GETATVER="${DOCKER_AUTOTEST_DIR}/config_value.py DEFAULTS autotest_version ${CFG}" \
    GETDTVER="${DOCKER_AUTOTEST_DIR}/config_value.py DEFAULTS config_version ${CFG}"
WORKDIR ${AUTOTEST_PATH}/client
# Can't use env. vars inside ENTRYPOINT
RUN chmod +x ${DOCKER_AUTOTEST_DIR}/config_value.py && \
    chmod +x /root/atomic_install.sh && \
    chmod +x /root/atomic_uninstall.sh && \
    ${GETATVER} > .autotest_version && \
    ${GETDTVER} > tests/docker/.dockertest_version
RUN export
# Setup harness versions the moment before execution but allow additional
# command line options from docker run
ENTRYPOINT ["/bin/sh","-c", \
            "git reset --hard `cat .autotest_version` && cd tests/docker && git reset --hard `cat .dockertest_version` && cd ${AUTOTEST_PATH}/client && ./autotest-local run docker"]
