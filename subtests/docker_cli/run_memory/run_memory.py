"""
Test output of docker run -m parameter

1. Run some containers with different memory values via parameter -m
2. Check if the container start or not as expected by sub-subtest

1. Run some containers with different memory values via parameter -m
2. Check if the container success start
  2.a If positive == 1, pass a random number which in the valid range
      and all the unit options, '', '0', 'b', 'B', 'k', 'K', 'm', 'M',
      'g','G'.Then check if the cgroup resource memory.limit_in_bytes match
      the memory, fail if both container start failed and memory
      mismatch its cgroup resource.
  2.b If positive == 0, pass three numbers: smaller than the minimum,
      larger than the maximal, invalid number, fail it the container
      success start.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import commands
import os

from autotest.client import utils
from autotest.client.shared import error
from dockertest import xceptions
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.dockercmd import MustFailDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCallerSimultaneous

class run_memory(SubSubtestCallerSimultaneous):

    """subtest Caller"""
    config_section = 'docker_cli/run_memory'

class run_memory_base(SubSubtest):

    """helper functions"""
    def check_memory(self, docker_memory, cgroup_memory, unit):
        """
        Compare container's memory which set by option -m, and its cgroup
        memory which is memory.limit_in_bytes that get from
        /sys/fs/cgroup/memory/docker/$long_id/ in this case
        :param docker_memory: docker memory set by the option --m
                              under "run" command
        :param cgroup_memory: docker's cgroup memory.
        """
        container_memory = int(docker_memory)
        cgroup_memory = int(cgroup_memory)

        if unit == 'K' or unit == 'k':
            container_memory *= 1024
        elif unit == 'm' or unit == 'M':
            container_memory *= 1024 * 1024
        elif unit == 'g' or unit == 'G':
            container_memory *= 1024 * 1024 * 1024

        if container_memory != cgroup_memory:
            result = {'FAIL':"container_memory is %s "
                             ",unit %s, cgroup_memory is %s"
                             % (container_memory, unit, cgroup_memory)}
            return result
        else:
            result = {'PASS':"container_memory is %s, "
                             "unit %s, cgroup_memory is %s"
                             % (container_memory, unit, cgroup_memory)}
            return result

    def container_json(self, name, content):
        """
        Return container's json value.
        :param name: An existing container's name
        :param content: What the json value need get
        """
        inspect_id_args = ['--format={{.%s}}' % content]
        inspect_id_args.append(name)
        container_json = NoFailDockerCmd(self.parent_subtest,
                                           'inspect',
                                            inspect_id_args)
        content_value = container_json.execute().stdout.strip()

        return content_value

    def combine_subargs(self, name, option, image, sub_command):
        """
        Combine a list of args the docker command needed.
        e.g. --name=test -m 1000M $image /bin/bash
        :param name: a name for container, pass it to option --name
        :param option: a memory option for container.
        :param image: an image name.
        :param sub_command: the sub command that the container need to be run.
        """
        subargs = []
        subargs.append('--name=%s' % name)
        subargs.append('-m %s' % option)
        subargs.append(image)
        subargs.append(sub_command)
        return subargs

    def read_cgroup(self, long_id, path, content):
        """
        Read container's cgroup value, return False if it doesn't exist.
        :param long_id: a container's long id, can get via command --inspect
        :param path: the cgroup path of container
        :param content: the value need read
        """
        cgroup_path = "%s/%s/%s" % (path, long_id, content)

        if os.path.exists(cgroup_path):
            cgroup_value = commands.getoutput('cat %s' % cgroup_path)
            return cgroup_value
        else:
            return False

    def extract_unit(self, memory):
        """
        Help extract the unit from some memory like 512M.
        :param memory: a list or a string value contains memory value.
        """
        unit = str(memory[-1])
        if unit.isalpha():
            return unit
        else:
            return ""

    def initialize(self):
        super(run_memory_base, self).initialize()
        docker_containers = DockerContainers(self.parent_subtest)
        image = DockerImage.full_name_from_defaults(self.config)
        unit_list = ['', 'b', 'B', 'k', 'K', 'm', 'M', 'g', 'G']
        memory_list = []
        self.sub_stuff['name'] = []
        args = []

        if self.config['expect_success'] == "PASS":
            memory_value = str(self.config['memory_value'])
            if memory_value is not '0':
                for unit in unit_list:
                    memory_list.append(memory_value + unit)
            else:
                memory_list.append('0')
        else:
            memory_list.append(self.config['memory_min_invalid'])
            memory_list.append(self.config['memory_max_invalid'])
            memory_list.append(self.config['memory_invalid'])

        for memory in memory_list:
            prefix = self.config['memory_name_prefix']
            name = docker_containers.get_unique_name(prefix, length=4)
            if self.config['expect_success'] == "PASS":
                self.sub_stuff['name'].append(name)
            args.append(self.combine_subargs(name,
                                             memory,
                                             image,
                                             '/bin/bash'))
        self.sub_stuff['subargs'] = args
        self.sub_stuff['container_memory'] = memory_list
        self.sub_stuff['cgroup_memory'] = []
        self.sub_stuff['result'] = []

    def run_once(self):
        super(run_memory_base, self).run_once()
        for subargs in self.sub_stuff['subargs']:
            if self.config['expect_success'] == "PASS":
                memory_container = NoFailDockerCmd(self.parent_subtest,
                                                'run',
                                                subargs).execute()
                self.loginfo(
                    "Executing docker command: %s" % memory_container)
                #Cut 'name' from "--name=$something",
                #then pass it to container_json
                long_id = self.container_json(str(subargs[0]).split('=')[1],
                                              'ID')
                #Cut memory value from "-m $memory"
                memory_value = str(subargs[1]).split(' ')[1]
                unit = self.extract_unit(memory_value)
                if unit is not False:
                    memory = memory_value.split(unit)[0]
                else:
                    memory = memory_value

                cgroup_memory = self.read_cgroup(
                                            long_id,
                                            self.config['cgroup_path'],
                                            self.config['cgroup_key_value'])
                #memory_no_cgroup test branch
                if memory is '0':
                    self.failif(cgroup_memory is not False,
                                "The path exist when set memory equals to 0")
                self.sub_stuff['result'].append(self.check_memory(memory,
                                                                cgroup_memory,
                                                                unit))
            else:
                memory_container = MustFailDockerCmd(self.parent_subtest,
                                                     'run',
                                                     subargs)
                self.loginfo(
                    "Executing docker command: %s" % memory_container)
                self.sub_stuff['result'] = memory_container.execute()

    def postprocess(self):
        super(run_memory_base, self).postprocess()
        fail_content = []
        fail_check = 0
        print self.sub_stuff['result']

        if self.config['expect_success'] == "PASS":
            for result in self.sub_stuff['result']:
                if list(result.keys())[0] is 'PASS':
                    self.loginfo(result.values())
                elif list(result.keys())[0] is 'FAIL':
                    self.logerror(result.values())
                    fail_content.append(result.values())
                    fail_check = True
                else:
                    raise xceptions.DockerTestNAError(
                         "Result %s is invalid" % result.keys()[0])
            self.failif(fail_check is True,
                        "Memory check mismatch ,%s" % fail_content)
        else:
            self.failif(self.sub_stuff['result'].exit_status != 0,
                        "Non-zero pull exit status: %s"
                        % self.sub_stuff['result'])

    def cleanup(self):
        super(run_memory_base, self).cleanup()
        if self.config['expect_success'] == "PASS":
            if self.config['remove_after_test']:
                for name in self.sub_stuff['name']:
                    dcmd = DockerCmd(self.parent_subtest,
                                         'rm',
                                         ['--force', name])
                    dcmd.execute()

class memory_positive(run_memory_base):
    """
    Test usage of docker 'run -m' command positively.

    Pass a number which read from the ini file and all the
    unit options, '', 'b', 'B', 'k', 'K', 'm', 'M', 'g','G'.
    Then check if the cgroup resource memory.limit_in_bytes
    matches the memory, fail if both container start unsuccessfully
    and memory mismatch its cgroup resource.
    """
    pass

class memory_no_cgroup(run_memory_base):
    """
    Test usage of docker 'run -m' command that sets memory to 0.

    Pass 0 to container as a memory value, which means don't use
    cgroup memory.limit_in_bytes.For now, fail if the cgroup exist or
    the container start unsuccessfully
    """
    pass

class memory_negative(run_memory_base):
    """
    Test usage of docker 'run -m' command negatively

    Pass three invalid memory value which smaller than min, larger
    than max, an invalid string one by one.To check if docker can
    handle the invalid parameter and the container should not start
    successfully.
    """
    pass
