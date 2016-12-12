# The value of FROM is to be set by test from systemd.ini
FROM {dockerfile_base_image}
ADD /p4321-server.py /usr/bin/
RUN chmod 755 /usr/bin/p4321-server.py
EXPOSE 4321
USER daemon
ENTRYPOINT ["/usr/bin/p4321-server.py"]
