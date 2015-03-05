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
# Note:
#    The image and container name "docker_autotest" is excluded from testing
#    by default.  It is not recommended to run more than one docker autotest
#    container at the same time.
#
# For Custom config, results, & tests, provide volumes for:
#     $CONFIG_CUSTOM_DIR, $CUSTOM_PRETESTS_DIR, $CUSTOM_INTRATESTS_DIR,
#     $CUSTOM_POSTTESTS_DIR, and/or $RESULTS_DIR
################################################################################
FROM stackbrew/centos:7
MAINTAINER cevich@redhat.com
# TODO: Add LABEL INSTALL and LABEL UNINSTAL
# TODO: make use of CONFDIR LOGDIR DATADIR
LABEL RUN="/usr/bin/docker run -it --rm --privileged --net=host --ipc=host --pid=host \
           --name docker_autotest docker_autotest"
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
RUN yum --disablerepo=*-eus-* --disablerepo=*-htb-* --disablerepo=*-ha-* --disablerepo=*-rt-* --disablerepo=*-lb-* --disablerepo=*-rs-* --disablerepo=*-sap-* --disablerepo=*beta* install -y deltarpm yum-utils
RUN yum-config-manager --disable *-eus-* *-htb-* *-ha-* *-rt-* *-lb-* *-rs-* *-sap-* *beta*
RUN yum -y update && yum -y install ${INSTALL_RPMS}
RUN "[" -n "${EPEL_URL}" ] && yum install -y ${EPEL_URL} && yum-config-manager --disable epel &> /dev/null
RUN "[" -n "${EPEL_URL}" ] && [ -n "${EPEL_RPMS}" ] && yum --enablerepo=epel install -y ${EPEL_RPMS}
################################################################################
# Environment setup
################################################################################
ENV AUTOTEST_PATH="/usr/local/autotest" \
    AUTOTEST_URL="https://github.com/autotest/autotest.git" \
    DOCKER_AUTOTEST_URL="https://github.com/autotest/autotest-docker.git"
ENV RESULTS_PATH=${AUTOTEST_PATH}/client/results \
    DOCKER_AUTOTEST_PATH=${AUTOTEST_PATH}/client/tests/docker
ENV CONFIG_CUSTOM_DIR=${DOCKER_AUTOTEST_PATH}/config_custom \
    CUSTOM_TESTS_DIR=${DOCKER_AUTOTEST_PATH}/subtests/custom \
    PRETESTS_DIR=${DOCKER_AUTOTEST_PATH}/pretests/custom \
    INTRATESTS_DIR=${DOCKER_AUTOTEST_PATH}/intratests/custom \
    POSTTESTS_DIR=${DOCKER_AUTOTEST_PATH}/posttests/custom
RUN export
################################################################################
# Version-independent test harness installation
################################################################################
# Allows version chang through runntime configuration (see below)
RUN git clone --single-branch ${AUTOTEST_URL} ${AUTOTEST_PATH}
RUN git clone --single-branch ${DOCKER_AUTOTEST_URL} ${DOCKER_AUTOTEST_PATH}
# Not included with every version of docker autotest
ADD config_value.py ${DOCKER_AUTOTEST_PATH}/
################################################################################
# Runtime Setup
################################################################################
WORKDIR ${AUTOTEST_PATH}/client
# Content of config_custom/defaults.ini at runtime is unpredictable,
# reset code to configured versions during runtime.  Permits one image
# to be used for multiple test runs against different versions of docker autotest
ENV CFG tests/docker/config_defaults/defaults.ini \
        tests/docker/config_custom/defaults.ini
ENV GETATVER tests/docker/config_value.py DEFAULTS autotest_version ${CFG}
ENV GETDTVER tests/docker/config_value.py DEFAULTS config_version ${CFG}
RUN ${GETATVER} > .autotest_version
RUN ${GETDTVER} > tests/docker/.dockertest_version
# Setup harness versions the moment before execution but allow additional
# command line options from docker run
ENTRYPOINT ["/bin/sh","-c", \
            "git reset --hard `cat .autotest_version` && cd tests/docker && git reset --hard `cat .dockertest_version` && cd ${AUTOTEST_PATH}/client && ./autotest-local run docker"]
