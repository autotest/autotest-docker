# TODO: Fill in FROM w/ in test code
FROM empty_base_image
MAINTAINER cevich@redhat.com
ADD basic_tree.tar /
ADD basic_devices.tar /
ENV PATH /usr/sbin:/usr/bin
# This is bugged since sbin is a symlink command will hang forever
# leaving it broken!
ADD busybox /usr/sbin/
RUN ["/usr/sbin/busybox", "sh", "-c", "echo Ho ho ho!"]
RUN ["this_shoud_fail"]
