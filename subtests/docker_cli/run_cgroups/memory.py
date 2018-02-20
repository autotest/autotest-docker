"""
Simple tests that check output/behavior of ``docker run`` wuth ``-m``
parameter.  It verifies that the container's cgroup resources
match value passed and if the container can handle invalid values
properly.
"""

from dockertest import xceptions
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass, mustfail, OutputNotBad
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
        # Probably because of "-m 0". RHEL <= 7.2 reported 0x7FF...FFFF in
        # .../cgroup/.../memory.limit_in_bytes, RHEL >= 7.3 reports 0x...F000.
        if cgroup_memory >= 0x7FFFFFFFFFFFF000:
            cgroup_memory = 0

        if unit == 'K' or unit == 'k':
            container_memory *= 1024
        elif unit == 'm' or unit == 'M':
            container_memory *= 1024 * 1024
        elif unit == 'g' or unit == 'G':
            container_memory *= 1024 * 1024 * 1024

        msg = ("cgroup memory is 0x%X, expected 0x%X (%s%s)" %
               (cgroup_memory, container_memory, docker_memory, unit.strip()))
        if container_memory == cgroup_memory:
            return {'PASS': msg}
        return {'FAIL': msg}

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
            if memory_value != '0':
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
            self.sub_stuff['mem_cntnr_name'] = name
            if self.config['expect_success'] == "PASS":
                self.sub_stuff['name'].append(name)
            args.append(self.combine_subargs(name,
                                             memory,
                                             image,
                                             '/bin/bash'))
        self.sub_stuff['subargs'] = args
        self.sub_stuff['container_memory'] = memory_list
        self.sub_stuff['memory_containers'] = []
        self.sub_stuff['cgroup_memory'] = []

    def run_once(self):
        super(memory_base, self).run_once()
        memory_containers = self.sub_stuff['memory_containers']
        for subargs in self.sub_stuff['subargs']:
            dkrcmd = DockerCmd(self, 'run -d -i', subargs)
            dkrcmd.execute()
            if self.config['expect_success'] == 'PASS':
                mustpass(dkrcmd)
            else:
                mustfail(dkrcmd, 125)
            memory_containers.append(dkrcmd)

    def check_result(self, subargs, long_id):
        """Return dictionary of results from check_memory()"""
        arg = self.get_arg_from_arglist(subargs, '-m')
        memory_arg = self.get_value_from_arg(arg, ' ', 1)
        memory = self.split_unit(memory_arg)
        memory_value = memory[0]
        memory_unit = memory[1]
        cgvalue = self.config['cgroup_key_value']
        cgroup_memory = self.read_cgroup(long_id, cgvalue)
        return self.check_memory(memory_value, cgroup_memory, memory_unit)

    def postprocess_positive(self, this_result, passed):
        if this_result is None:
            raise xceptions.DockerTestError("Invoked with null results")
        self.failif(not isinstance(this_result, dict),
                    ("expected this_result to be a dict; it's a %s" %
                     this_result.__class__))
        status = this_result.keys().pop()
        if status == "PASS":
            self.logdebug(this_result)
            passed.append(True)
        elif status == 'FAIL':
            self.logerror(this_result)
            passed.append(False)
        else:
            raise xceptions.DockerTestError("%s invalid result %s"
                                            % this_result)

    def postprocess_negative(self, this_result, memory_container, passed):
        if this_result is not None:  # Verify failed
            self.failif(not isinstance(this_result, dict),
                        ("expected this_result to be a dict; it's a %s" %
                         this_result.__class__))
            status = this_result.keys().pop()
            if status == "FAIL":
                self.logdebug("Expected fail: %s", this_result)
                passed.append(True)
            elif status == 'FAIL':
                self.logerror("Unexpected pass: %s", this_result)
                passed.append(False)
            else:
                raise xceptions.DockerTestError("%s invalid result %s"
                                                % this_result)
        else:  # cgroups could not be checked
            cmdresult = memory_container.cmdresult
            exit_status = cmdresult.exit_status
            if exit_status is None:
                self.logerror("Unexpected running container: %s",
                              memory_container)
                passed.append(False)
                return
            # Verify no crashes or oopses
            OutputNotBad(cmdresult)
            # Non-zero exit should produce usage/error message
            if exit_status == 0:
                self.logerror("Unexpected success: %s" % cmdresult)
                passed.append(False)
            else:
                self.logdebug("Expected failure: %s" % cmdresult)
                passed.append(True)

    def postprocess(self):
        super(memory_base, self).postprocess()
        passed = []
        memory_containers = self.sub_stuff['memory_containers']
        for index, memory_container in enumerate(memory_containers):
            subargs = self.sub_stuff['subargs'][index]
            try:
                # Throws IndexError
                long_id = memory_container.stdout.splitlines()[0].strip()
                # Throws DockerIOError
                this_result = self.check_result(subargs, long_id)
            except (IndexError, xceptions.DockerIOError) as e:
                self.logwarning("Ignoring exception: %s" % e)
                this_result = None
            if self.config['expect_success'] == "PASS":
                self.postprocess_positive(this_result, passed)
            else:  # self.config['expect_success'] == "FAIL":
                self.postprocess_negative(this_result,
                                          memory_container, passed)
        self.failif(not all(passed), "One or more checks failed")
