r"""
Summary
-------

Test the rhel-push-plugin, which blocks push of RHEL-based
images to docker.io

Operational Summary
-------------------

#. Build an image claiming to be (or not to be) RHEL-based
#. Tag it, try to push it
#. If RHEL-based, expect failure message from plugin.
"""

import os
from dockertest.images import DockerImages
from dockertest.subtest import SubSubtest
from dockertest.dockercmd import DockerCmd
from dockertest import subtest


class rhel_push_plugin(subtest.SubSubtestCaller):

    """ SubSubtest caller """

    def initialize(self):
        self.failif_not_redhat()
        super(rhel_push_plugin, self).initialize()


class rhel_push_plugin_base(SubSubtest):

    def initialize(self):
        super(rhel_push_plugin_base, self).initialize()

        # FIXME: raise DockerTestNAError if rhel-push-plugin not running?
        # This isn't trivial: if we try systemctl status, we have to check
        # docker and docker-latest; using ps (or /proc or psutil) might
        # be a better option.
        #
        # References:
        #  https://zignar.net/2014/09/08/getting-started-with-dbus-python-systemd/
        #  https://pythonhosted.org/psutil/
        self.sub_stuff['base_image'] = self.config['base_image']
        self.sub_stuff['dockerfile'] = self.dockerfile()
        self.sub_stuff['image_name'] = DockerImages(self).get_unique_name()
        self.sub_stuff['dest_name'] = self.config['dest_name']

    def run_once(self):
        super(rhel_push_plugin_base, self).run_once()

        image_name = self.sub_stuff['image_name']
        dest_name = self.sub_stuff['dest_name']
        docker_cmds = [
            ['build', ['-t', image_name, self.tmpdir], 0],
            ['tag',   [image_name, dest_name],         0],
            ['push',  [dest_name],                     1],
        ]
        for cmd in docker_cmds:
            docker_cmd = DockerCmd(self, cmd[0], cmd[1])
            result = docker_cmd.execute()
            self.failif_ne(result.exit_status, cmd[2],
                           "Exit code from docker %s %s; stderr='%s'" % (
                               cmd[0], cmd[1], result.stderr))

        if self.config['expected_stderr']:
            self.failif_not_in(self.config['expected_stderr'], result.stderr,
                               "expected stderr from docker push")

    def cleanup(self):
        super(rhel_push_plugin_base, self).cleanup()
        for k in 'image_name', 'dest_name', 'base_image':
            dcmd = DockerCmd(self, 'rmi', [self.sub_stuff[k]])
            dcmd.execute()

    def dockerfile(self):
        """
        Create a Dockerfile with desired labels in our scratch directory.
        """
        dockerfile = os.path.join(self.tmpdir, 'Dockerfile')
        with open(dockerfile, 'wb') as dockerfile_fh:
            dockerfile_fh.write("""FROM {base_image}
MAINTAINER nobody@redhat.com
LABEL Vendor="{image_vendor}"
LABEL Name="{image_name}"
RUN echo hi
""".format(**self.config))

        return dockerfile


class push_blocked(rhel_push_plugin_base):
    """
    The primary test: a RHEL-based image will be rejected.
    """
    pass


class push_vendor_ok(rhel_push_plugin_base):
    """
    If vendor != Red Hat, Inc., it's not a RHEL-based image and it
    should be allowed to push.
    """
    pass


class push_name_ok(rhel_push_plugin_base):
    """
    If image name doesn't begin with 'rhel', it's not a RHEL-based image
    and it should be allowed to push.
    """
    pass


class push_registry_ok(rhel_push_plugin_base):
    """
    It's a RHEL-based image, but the destination isn't docker.io, so
    it should be allowed to push.
    """
    pass
