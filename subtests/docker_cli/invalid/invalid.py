r"""
Summary
---------

Test output of docker run command with invalid characters

Operational Summary
----------------------

#. Run a container using invalid charactor in
   "docker run [OPTIONS] IMAGE [COMMAND] [ARG...]"
#. Execute docker run command, different subtest has different subargs and
   subargs order.
#. Check test result: What we expected is the all of the test results are
   failed.
#. Clean the test environment and remove the container generated in testing.
"""

from dockertest import subtest
from dockertest import config
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from autotest.client import utils


class invalid(subtest.SubSubtestCallerSimultaneous):
    config_section = 'docker_cli/invalid'


class invalid_base(subtest.SubSubtest):

    def initialize(self):
        super(invalid_base, self).initialize()

        self.sub_stuff['tag'] = []
        self.sub_stuff['container_names'] = []

        self.sub_stuff['arg_inpars'] = []
        self.sub_stuff['arg_invals'] = []

        self.sub_stuff['result_inparam'] = False
        self.sub_stuff['result_invalus'] = False

        fin = []
        arg_inpars = []
        arg_invals = []

        config.none_if_empty(self.config)
        invalidparams = self.config['invalid_run_params']
        invalidvalues = self.config['invalid_run_values']

        for inp in invalidparams.split(','):
            arg_inpars.append(inp)

        for inv in invalidvalues.split(','):
            arg_invals.append(inv)

        if self.config['input_docker_tag']:
            fin = DockerImage.full_name_from_defaults(self.config)
            self.sub_stuff['tag'].append(fin)

        self.sub_stuff['arg_inpars'] = arg_inpars
        self.sub_stuff['arg_invals'] = arg_invals

    @staticmethod
    def array_args(section, conf_arg, arg1, arg2):
        args = []
        if section == 'option':
            args = conf_arg + arg1 + arg2
        elif section == 'image':
            args = conf_arg + arg1 + arg2
        elif section == 'command':
            args = arg1 + arg2 + conf_arg
        elif section == 'args':
            args = arg1 + arg2 + conf_arg
        else:
            args = conf_arg + arg1
        return args

    def add_arg_run(self, section, slist, arg1):
        cmdresults = []

        for arg in slist:
            container_name = []
            container_name.append((utils.generate_random_string(12)))

            args = self.array_args(section,
                                   [arg],
                                   ['--name'] + container_name,
                                   arg1)
            nfdc = DockerCmd(self, "run", args)
            cmdresult = nfdc.execute()

            cmdresults.append(cmdresult)
            self.sub_stuff['container_names'].append(container_name)

        return cmdresults

    def run_once(self):
        super(invalid_base, self).run_once()
        cmdresult_inpara = []
        cmdresult_invals = []

        arg_inpars_lst = self.sub_stuff['arg_inpars']
        arg_invals_lst = self.sub_stuff['arg_invals']

        self.logdebug("Test the invalid charactors for the parameter")
        cmdresult_inpara = self.add_arg_run(self.config['section'],
                                            arg_inpars_lst,
                                            self.sub_stuff['tag'])
        self.logdebug("Test the invalid charactors for the parameter value")
        cmdresult_invals = self.add_arg_run(self.config['section'],
                                            arg_invals_lst,
                                            self.sub_stuff['tag'])
        self.sub_stuff['cmdresult_inpara'] = cmdresult_inpara
        self.sub_stuff['cmdresult_invals'] = cmdresult_invals

    def outputcheck(self):
        exp_out_inpara = self.config['invalid_pars_expected_output']
        exp_out_invals = self.config['invalid_vals_expected_output']

        for cmdresult in self.sub_stuff['cmdresult_inpara']:
            if exp_out_inpara not in str(cmdresult):
                self.sub_stuff['result_inparam'] |= True
                self.logerror("Failed to find expected '%s'."
                              % exp_out_inpara)
            else:
                self.logdebug("Successfully found expected '%s'."
                              % exp_out_inpara)

        for cmdresult in self.sub_stuff['cmdresult_invals']:
            if exp_out_invals not in str(cmdresult):
                self.sub_stuff['result_invalus'] |= True
                self.logerror("Failed to find expected '%s'."
                              % exp_out_invals)
            else:
                self.logdebug("Successfully found expected '%s'."
                              % exp_out_invals)

    def postprocess(self):
        super(invalid_base, self).postprocess()
        self.outputcheck()

        ret = False
        ret |= self.sub_stuff['result_inparam']
        ret |= self.sub_stuff['result_invalus']

        for cmdresult in self.sub_stuff['cmdresult_inpara']:
            self.logdebug(cmdresult)
        for cmdresult in self.sub_stuff['cmdresult_invals']:
            self.logdebug(cmdresult)

        self.failif(ret,
                    "FAIL - The docker command with the invalid charactors"
                    "is available!!! The expected result is invalid!")

    def cleanup(self):
        super(invalid_base, self).cleanup()
        for container in self.sub_stuff['container_names']:
            cm = DockerCmd(self, "rm", container)
            cm.execute()
