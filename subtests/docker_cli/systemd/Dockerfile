FROM centos:latest
RUN yum install -y python && \
    yum update -y && \
    yum clean all
ADD /p4321-server.py /usr/bin/
RUN chmod 755 /usr/bin/p4321-server.py
EXPOSE 4321
USER daemon
ENTRYPOINT ["/usr/bin/p4321-server.py"]
