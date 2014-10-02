"""
Simple tests that check output/behavior of ``docker run`` wuth ``-c``
parameter.  It verifies that the container's cgroup resources
match value passed and if the container can handle invalid values
properly.
"""

from dockertest import xceptions
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.images import DockerImage
from cgroups_base import cgroups_base


class cpu_base(cgroups_base):

    @staticmethod
    def check_cpushares(docker_cpushares, cgroup_cpushares, json_cpushares):
        """
        Compare container's cpu shares set by option -c, and its cgroup
        cpu.shares

        :param docker_cpushares: Value supplied to docker
        :param cgroup_cpushares: Value reported in cgroup file
        :param json_cpushares: Value reported in docker inspect
        :return: Dictionary containing PASS/FAIL key with details
        """
        docker_cpushares = int(docker_cpushares)
        cgroup_cpushares = int(cgroup_cpushares)
        json_cpushares = int(json_cpushares)
        msg = ("Container cpu shares: %s, "
               "cgroup cpu shares: %s, "
               "inspect cpu shares %s"
               % (docker_cpushares, cgroup_cpushares, json_cpushares))
        # therefor cgroup_cpushares == json_cpushares
        matches = [docker_cpushares == cgroup_cpushares,
                   docker_cpushares == json_cpushares]
        if all(matches):
            return {'PASS': msg, 'FAIL': None}
        else:
            return {'FAIL': msg, 'PASS': None}

    def initialize(self):
        super(cpu_base, self).initialize()
        dc = self.sub_stuff['docker_containers']
        image = DockerImage.full_name_from_defaults(self.config)
        cpushares_value = self.config.get('cpushares_value', None)
        if cpushares_value is None:
            subargs = []
        else:
            subargs = ['--cpu-shares=%s' % cpushares_value]
        name = self.sub_stuff['name'] = dc.get_unique_name()
        subargs += ['--name=%s' % name,
                    '--detach',
                    '--tty',
                    image,
                    '/bin/bash']
        self.sub_stuff['subargs'] = subargs
        self.sub_stuff['result'] = []

    def run_once(self):
        super(cpu_base, self).run_once()
        subargs = self.sub_stuff['subargs']
        dc = self.sub_stuff['docker_containers']
        NoFailDockerCmd(self, 'run', subargs).execute()
        cobjs = dc.list_containers_with_name(self.sub_stuff['name'])
        long_id = cobjs[0].long_id
        json_cpushares = dc.json_by_long_id(long_id)[0]["Config"]["CpuShares"]
        cgpath = self.config['cgroup_path']
        cgvalue = self.config['cgroup_key_value']
        cgroup_cpushares = self.read_cgroup(long_id, cgpath, cgvalue)
        docker_cpushares = self.config.get('cpushares_value', 0)
        self.sub_stuff['result'] = self.check_cpushares(docker_cpushares,
                                                        cgroup_cpushares,
                                                        json_cpushares)

    def postprocess(self):
        super(cpu_base, self).postprocess()
        result = self.sub_stuff['result']
        invalid = xceptions.DockerTestError("Invalid result %s" % result)
        if self.config['expect_success'] == "PASS":
            if result['FAIL'] is not None:
                raise xceptions.DockerTestFail(result)
            elif result['PASS'] is not None:
                self.logdebug(result)
            else:
                raise invalid
        else:
            self.loginfo("Command expected to fail!")
            if result['PASS'] is not None:
                raise xceptions.DockerTestFail(result)
            elif result['FAIL'] is not None:
                self.logdebug(result)
            else:
                raise invalid

    def cleanup(self):
        # Expects list of names to remove
        self.sub_stuff['name'] = [self.sub_stuff['name']]
        super(cpu_base, self).cleanup()
