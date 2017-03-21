FROM registry.access.redhat.com/rhel7/rhel:latest
MAINTAINER cevich@redhat.com
ENV PATH /usr/sbin:/usr/bin
RUN echo "Schazam!"
RUN /bin/false
RUN echo "foobar" > /var/tmp/testfile
RUN cat /var/tmp/testfile
