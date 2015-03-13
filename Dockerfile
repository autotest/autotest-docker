FROM stackbrew/centos:7
MAINTAINER cevich@redhat.com
################################################################################
# Configuration Options
################################################################################
ENV VERBOSE="yes" \
    HOST_ROOT="/var/lib" \
    AUTOTEST_URL="https://github.com/autotest/autotest.git" \
    DOCKER_AUTOTEST_URL="https://github.com/autotest/autotest-docker.git" \
    DOCKER_AUTOTEST_BRANCH="master" \
    REPO_INSTALL="yum install -y \
http://linux.mirrors.es.net/fedora-epel/7/x86_64/e/epel-release-7-5.noarch.rpm" \
    INSTALL_RPMS="procps tar findutils bzip2 gdb bridge-utils coreutils \
nfs-utils git glibc-devel python-sphinx python-bugzilla" \
    AUTOTEST_PATH="/usr/local/autotest" \
    DOCKER_AUTOTEST_PATH="/usr/local/autotest/client/tests/docker" \
    DOCKER_BIN_PATH="/usr/bin/docker"
################################################################################
LABEL INSTALL="/usr/bin/docker run \
--interactive \
--tty \
--rm \
--privileged \
--net=host \
--ipc=host \
--pid=host \
--env HOST=/host \
--env NAME=NAME \
--env IMAGE=IMAGE \
--volume /run:/run \
--volume /var/log:/var/log \
--volume /:/host \
IMAGE \
tests/docker/atomic/atomic_install.sh"
################################################################################
RUN yum --disablerepo="*-eus-*" --disablerepo="*-htb-*" --disablerepo="*-ha-*" \
        --disablerepo="*-rt-*" --disablerepo="*-lb-*" --disablerepo="*-rs-*" \
        --disablerepo="*-sap-*" --disablerepo="*beta*" \
        install -y deltarpm yum-utils && \
    yum-config-manager --disable "*-eus-*" "*-htb-*" "*-ha-*" "*-rt-*" \
        "*-lb-*" "*-rs-*" "*-sap-*" "*beta*" &> /dev/null && \
    yum update -y && \
    ${REPO_INSTALL} && \
    yum install -y ${INSTALL_RPMS} && \
    yum clean all
RUN git clone --single-branch ${AUTOTEST_URL} ${AUTOTEST_PATH}
WORKDIR ${AUTOTEST_PATH}/client
RUN git clone --single-branch --branch ${DOCKER_AUTOTEST_BRANCH} \
        ${DOCKER_AUTOTEST_URL} ${DOCKER_AUTOTEST_PATH} && \
    echo -e "\nBuild complete, install with: atomic install <image>"
