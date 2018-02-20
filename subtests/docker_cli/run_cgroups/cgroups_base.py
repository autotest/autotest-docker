"""
Base class for cgroups testing
"""

import os
from dockertest import xceptions
from dockertest.output import mustpass, DockerVersion
from dockertest.dockercmd import DockerCmd
from dockertest.containers import DockerContainers
from dockertest.subtest import SubSubtest
from dockertest.config import get_as_list


class cgroups_base(SubSubtest):

    def cgroup_fullpath(self, long_id, content):
        """
        Return full cgroup path for a container.
        :param long_id: a container's long id
        :cgroup_type: desired cgroup type ('cpu' or 'memory')
        :param content: the value need check.
        """
        cgroup_base_dir = '/sys/fs/cgroup'
        # 'cpu' or 'memory', extracted from test name
        cgroup_type = self.__class__.__name__.split('_')[0]
        (parent, subdir) = ('system.slice', 'docker-{}.scope')
        if DockerVersion().is_podman:
            (parent, subdir) = ('libpod_parent', 'libpod-{}/ctr')
        return os.path.join(cgroup_base_dir, cgroup_type, parent,
                            subdir.format(long_id), content)

    def read_cgroup(self, long_id, content):
        """
        Read container's cgroup file, return its value
        :param long_id: a container's long id, can get via command --inspect.
        :param path: the cgroup path of container.
        :param content: the value need read.
        """
        cgroup_path = self.cgroup_fullpath(long_id, content)
        if not os.path.exists(cgroup_path):
            raise xceptions.DockerIOError("Docker cgroup path "
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
            preserve_cnames = get_as_list(self.config['preserve_cnames'])
            for name in self.sub_stuff.get('name', []):
                if name not in preserve_cnames:
                    DockerCmd(self, 'rm', ['--force', name]).execute()
