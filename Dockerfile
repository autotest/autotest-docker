# Simple dockerfile needed by some tests
# to build from a static http/https/git location
FROM stackbrew/centos:centos7
RUN echo "Some ECHO line." > /tmp/file
RUN cat /tmp/file
