"""
Simple tests that check output/behavior of ``docker run`` wuth ``-m``
parameter.  It verifies that the container's cgroup resources
match value passed and if the container can handle invalid values
properly.
"""

from dockertest import xceptions
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.output import mustfail
from dockertest.images import DockerImage
from cgroups_base import cgroups_base


class memory_base(cgroups_base):

    @staticmethod
    def check_memory(docker_memory, cgroup_memory, unit):
        """
        Compare container's memory set by option -m, and its cgroup
        memory.limit_in_bytes

        :param docker_memory: docker memory set -m option
        :param cgroup_memory: docker's cgroup memory.
        :param unit: Single case-sensitive unit designation ('K', 'm', etc)
        :return: Dictionary containing PASS/FAIL key with details
        """
        container_memory = int(docker_memory)
        cgroup_memory = int(cgroup_memory)
        if cgroup_memory == 9223372036854775807:
            cgroup_memory = 0

        if unit == 'K' or unit == 'k':
            container_memory *= 1024
        elif unit == 'm' or unit == 'M':
            container_memory *= 1024 * 1024
        elif unit == 'g' or unit == 'G':
            container_memory *= 1024 * 1024 * 1024

        if container_memory == 0:
            if cgroup_memory == 0:
                msg = ("container_memory is %s, "
                       "unit %s, cgroup_memory is %s"
                       % (container_memory, unit, cgroup_memory))
                result = {'PASS': msg}

                return result
            else:
                msg = ("container_memory is %s, "
                       "unit %s, cgroup_memory is %s, status Unknown"
                       % (container_memory, unit, cgroup_memory))
                result = {'FAIL': msg}

                return result

        if container_memory != cgroup_memory:
            msg = ("container_memory is %s "
                   ",unit %s, cgroup_memory is %s"
                   % (container_memory, unit, cgroup_memory))
            result = {'FAIL': msg}
            return result
        else:
            msg = ("container_memory is %s, "
                   "unit %s, cgroup_memory is %s"
                   % (container_memory, unit, cgroup_memory))
            result = {'PASS': msg}
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

    def initialize(self):
        super(memory_base, self).initialize()
        docker_containers = self.sub_stuff['docker_containers']
        image = DockerImage.full_name_from_defaults(self.config)
        unit_list = ['', 'b', 'B', 'k', 'K', 'm', 'M', 'g', 'G']
        memory_list = []
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
            name = docker_containers.get_unique_name()
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
        super(memory_base, self).run_once()

        for subargs in self.sub_stuff['subargs']:
            if self.config['expect_success'] == "PASS":
                memory_container = mustpass(DockerCmd(self,
                                                      'run -d -t',
                                                      subargs).execute())
                long_id = self.container_json(str(subargs[0]).split('=')[1],
                                              'Id')
                memory_arg = self.get_value_from_arg(
                    self.get_arg_from_arglist(subargs, '-m'), ' ', 1)
                memory = self.split_unit(memory_arg)
                memory_value = memory[0]
                memory_unit = memory[1]

                cgpath = self.config['cgroup_path']
                cgvalue = self.config['cgroup_key_value']
                cgroup_memory = self.read_cgroup(long_id, cgpath, cgvalue)
                self.sub_stuff['result'].append(self.check_memory(
                    memory_value, cgroup_memory, memory_unit))
            else:
                memory_container = mustfail(DockerCmd(self,
                                                      'run',
                                                      subargs))
                # throws exception if exit_status == 0
                self.sub_stuff['result'] = memory_container.execute()

    def postprocess(self):
        super(memory_base, self).postprocess()
        fail_content = []
        fail_check = 0
        self.logdebug('Result: %s', self.sub_stuff['result'])
        clsname = self.__class__.__name__

        if self.config['expect_success'] == "PASS":
            for result in self.sub_stuff['result']:
                if list(result.keys())[0] is 'PASS':
                    self.logdebug(result.values())
                elif list(result.keys())[0] is 'FAIL':
                    self.logerror("%s failure result value %s",
                                  clsname, result.values())
                    fail_content.append(result.values())
                    fail_check = True
                else:
                    raise xceptions.DockerTestNAError("%s invalid result %s"
                                                      % (clsname,
                                                         result.keys()[0]))
            self.failif(fail_check is True,
                        "%s memory check mismatch %s"
                        % (clsname, fail_content))
        else:
            self.failif(self.sub_stuff['result'].exit_status == 0,
                        "%s unexpected zero exit status: %s"
                        % (clsname, self.sub_stuff['result']))
