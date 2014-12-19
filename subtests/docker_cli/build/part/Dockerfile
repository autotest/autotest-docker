FROM scratch
MAINTAINER cevich@redhat.com
ADD basic_tree.tar /
ADD basic_devices.tar /
ENV PATH /usr/sbin:/usr/bin
ADD busybox /usr/sbin/
RUN ["/usr/sbin/busybox", "sh", "-c", "for item in $(busybox --list-full); do busybox ln -s /usr/sbin/busybox $item; done"]
RUN echo "Schazam!"
