"""
Test output of docker run -m parameter

1. Run some containers with different memory values via parameter -m
2. Check if the container start or not as expected by sub-subtest

1. Run some containers with different memory values via parameter -m
2. Check if the container success start
  2.a If expect_success == PASS, pass a random number which in the valid range
      and all the unit options, '', '0', 'b', 'B', 'k', 'K', 'm', 'M',
      'g','G'.Then check if the cgroup resource memory.limit_in_bytes match
      the memory, fail if both container start failed and memory
      mismatch its cgroup resource.
  2.b If expect_success == FAIL, pass three numbers: smaller than the minimum,
      larger than the maximal, invalid number, fail it the container
      success start.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import os
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

class run_memory_base(SubSubtest):

    """helper functions"""
    @staticmethod
    def check_memory(docker_memory, cgroup_memory, unit):
        """
        Compare container's memory which set by option -m, and its cgroup
        memory which is memory.limit_in_bytes that get from
        /sys/fs/cgroup/memory/system.slice/docker-$long_id.scope/ in this case
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

        if container_memory == 0:
            if cgroup_memory == 0:
                result = {'PASS':"container_memory is %s, "
                             "unit %s, cgroup_memory is %s"
                             % (container_memory, unit, cgroup_memory)}

                return result
            else:
                result = {'FAIL':"container_memory is %s, "
                             "unit %s, cgroup_memory is %s, status Unknown"
                             % (container_memory, unit, cgroup_memory)}

                return result

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

    @staticmethod
    def combine_subargs(name, option, image, sub_command):
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

    @staticmethod
    def read_cgroup(long_id, path, content,):
        """
        Read container's cgroup file, return its value
        :param long_id: a container's long id, can get via command --inspect.
        :param path: the cgroup path of container.
        :param content: the value need read.
        """
        cgroup_path = "%s-%s.scope/%s" % (path, long_id, content)
        cgroup_file = open(cgroup_path, 'r')
        try:
            cgroup_value = cgroup_file.read()
        finally:
            cgroup_file.close()

        return cgroup_value

    @staticmethod
    def check_cgroup_exist(long_id, path, content):
        """
        Test if container's cgroup exist.For now the path is
        /sys/fs/cgroup/$content/system.slice/docker-$long_id.scope
        :param long_id: a container's long id
        :path: the cgroup path of container
        :param content: the value need check.
        """
        cgroup_path = "%s-%s.scope/%s" % (path, long_id, content)

        if os.path.exists(cgroup_path):
            return True
        else:
            return False

    @staticmethod
    def get_arg_from_arglist(argslist, parameter):
        """
        Split single argument from a argslist, e.g will return '-m 5242889'
        from this list:
        ['--name=test_1GlH', '-m 5242889', 'mattdm/fedora:latest', '/bin/bash']
        when set parameter to '-m'
        :param argslist: a arg list, see abvoe.
        :param parameter: the arg need return, like memory '-m'.
        """
        temp_arg = []
        for subarg in argslist:
            if parameter in subarg:
                temp_arg = subarg

        return temp_arg

    @staticmethod
    def get_value_from_arg(arg, method, locate):
        """
        Split single parameter from a argument, e.g will return 5242889G
        from '-m 5242889' if method is ' ' and locate is 1.
        :param arg: Single argument, like '--name=test'.
        :param method: Split method, like ' ' or '='.
        :locate: parameter located.
        """
        temp_value = arg.split(method)[locate]

        return temp_value

    @staticmethod
    def split_unit(memory_value):
        """
        Split unit from memory_value, e.g once 5242889G passes into,
        will return a list ['5242889', 'G'].
        :param memory_value: a memory value.
        """
        memory = []
        unit = str(memory_value[-1])
        if unit.isalpha():
            memory.append(memory_value.split(unit)[0])
            memory.append(unit)
            return memory
        else:
            memory.append(memory_value)
            memory.append(' ')
            return memory

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
                                                'run -d -t',
                                                subargs).execute()
                self.logdebug(
                    "Executing docker command: %s" % memory_container)

                long_id = self.container_json(str(subargs[0]).split('=')[1],
                                              'ID')
                memory_arg = self.get_value_from_arg(
                                    self.get_arg_from_arglist(subargs, '-m'),
                                    ' ', 1)
                memory = self.split_unit(memory_arg)
                memory_value = memory[0]
                memory_unit = memory[1]

                cgroup_exist = self.check_cgroup_exist(long_id,
                                           self.config['cgroup_path'],
                                           self.config['cgroup_key_value'])
                if cgroup_exist is True:
                    cgroup_memory = self.read_cgroup(
                                            long_id,
                                            self.config['cgroup_path'],
                                            self.config['cgroup_key_value'])
                else:
                    xceptions.DockerTestNAError("Docker path doesn't exist!")

                self.sub_stuff['result'].append(self.check_memory(
                                                     memory_value,
                                                     cgroup_memory,
                                                     memory_unit))
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
            self.failif(self.sub_stuff['result'].exit_status == 0,
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
    cgroup memory.limit_in_bytes.For now, fail if the cgroup don't exist or
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
