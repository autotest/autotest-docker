FROM stackbrew/centos:7
MAINTAINER cevich@redhat.com
################################################################################
# Configuration Options
################################################################################
ENV VERBOSE="yes" \
    HOST_ROOT="/var/lib" \
    AUTOTEST_URL="https://github.com/autotest/autotest.git" \
    PROTECT_IMAGES="stackbrew/centos:7, stackbrew/centos:latest" \
    PROTECT_CONTAINERS="" \
    REPO_INSTALL="yum install -y \
http://linux.mirrors.es.net/fedora-epel/7/x86_64/e/epel-release-7-5.noarch.rpm" \
    INSTALL_RPMS="procps tar findutils bzip2 gdb bridge-utils \
nfs-utils git glibc-devel python-sphinx python-bugzilla" \
    AUTOTEST_PATH="/usr/local/autotest" \
    DOCKER_AUTOTEST_PATH="/usr/local/autotest/client/tests/docker" \
    DOCKER_BIN_PATH="/usr/bin/docker"
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
    yum clean all && \
    rm -rf /usr/share/doc/* && \
    rm -rf /usr/share/man/*
RUN git clone --single-branch ${AUTOTEST_URL} ${AUTOTEST_PATH}
WORKDIR ${AUTOTEST_PATH}/client
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
/usr/local/autotest/client/tests/docker/atomic/atomic_install.sh"
################################################################################
ADD / /${DOCKER_AUTOTEST_PATH}/
RUN git reset --hard $(${DOCKER_AUTOTEST_PATH}/atomic/config_value.py \
                       DEFAULTS autotest_version \
                       ${DOCKER_AUTOTEST_PATH}/config_defaults/defaults.ini \
                       ${DOCKER_AUTOTEST_PATH}/config_custom/defaults.ini) && \
    echo -e "\nComplete installation with 'atomic install IMAGE'\n"
