FROM scratch
MAINTAINER cevich@redhat.com
ADD basic_tree.tar /
ADD basic_devices.tar /
ENV PATH /usr/sbin:/usr/bin
ADD busybox /usr/sbin/
RUN ["/usr/sbin/busybox", "sh", "-c", "echo Ho ho ho!"]
RUN ["/usr/sbin/busybox", "false"]
