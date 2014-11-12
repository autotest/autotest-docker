"""
Base class for cgroups testing
"""

import os
from dockertest import xceptions
from dockertest.output import mustpass
from dockertest.dockercmd import DockerCmd
from dockertest.containers import DockerContainers
from dockertest.subtest import SubSubtest


class cgroups_base(SubSubtest):

    @staticmethod
    def cgroup_fullpath(long_id, path, content):
        """
        Return full cgroup path for a container.
        :param long_id: a container's long id
        :path: the cgroup path of container
        :param content: the value need check.
        """
        return os.path.join("%s-%s.scope" % (path, long_id), content)

    @staticmethod
    def read_cgroup(long_id, path, content):
        """
        Read container's cgroup file, return its value
        :param long_id: a container's long id, can get via command --inspect.
        :param path: the cgroup path of container.
        :param content: the value need read.
        """
        cgroup_path = cgroups_base.cgroup_fullpath(long_id, path, content)
        if not os.path.exists(cgroup_path):
            raise xceptions.DockerTestNAError("Docker cgroup path "
                                              "doesn't exist: %s"
                                              % cgroup_path)
        cgroup_file = open(cgroup_path, 'r')
        try:
            cgroup_value = cgroup_file.read()
        finally:
            cgroup_file.close()
        return cgroup_value

    def container_json(self, name, content):
        """
        Return container's json value.
        :param name: An existing container's name
        :param content: What the json value need get
        """
        inspect_id_args = ['--format={{.%s}}' % content]
        inspect_id_args.append(name)
        container_json = DockerCmd(self, 'inspect', inspect_id_args)
        content_value = mustpass(container_json.execute()).stdout.strip()

        return content_value

    def initialize(self):
        super(cgroups_base, self).initialize()
        self.sub_stuff['docker_containers'] = DockerContainers(self)
        self.sub_stuff['name'] = []

    def cleanup(self):
        super(cgroups_base, self).cleanup()
        if self.config['remove_after_test']:
            for name in self.sub_stuff.get('name', []):
                DockerCmd(self, 'kill', [name]).execute()
                DockerCmd(self, 'rm', ['--force', name]).execute()
