"""
Test output of docker start command

1. Create new container.
2. Wait till end of container command.
3. Try to start container.
4. Check if container was started.
"""

import time
from autotest.client.shared import error
from dockertest.subtest import SubSubtest
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd, DockerCmd
from dockertest.containers import DockerContainersCLI
from dockertest.images import DockerImage
from dockertest import subtest
from dockertest import config

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

class DockerContainersCLIWithOutSize(DockerContainersCLI):

    """
    DockerContainersCLIWithOutSize remove size checking from
    DockerContainersCLI for cmd time reduction.
    """

    #: This is probably test-subject related, be a bit more noisy
    verbose = True

        # private methods don't need docstrings
    def _get_container_list(self):  # pylint: disable=C0111
        return self.docker_cmd("ps -a --no-trunc",
                               self.timeout)


class DockerContainersCLIRunOnly(DockerContainersCLIWithOutSize):

    """
    DockerContainersCLI remove size checking from DockerContainersCLI.
    It takes lots of time. Only running containers.
    """

    #: This is probably test-subject related, be a bit more noisy
    verbose = True

        # private methods don't need docstrings
    def _get_container_list(self):  # pylint: disable=C0111
        return self.docker_cmd("ps --no-trunc",
                               self.timeout)


class start(subtest.SubSubtestCaller):
    config_section = 'docker_cli/start'


class start_base(SubSubtest):

    def initialize(self):
        super(start_base, self).initialize()
        config.none_if_empty(self.config)
        dc = DockerContainersCLIWithOutSize(self.parent_subtest)
        self.sub_stuff["conts_obj"] = dc
        dc = DockerContainersCLIRunOnly(self.parent_subtest)
        self.sub_stuff["con_ro_obj"] = dc

        self.sub_stuff["image_name"] = None
        self.sub_stuff["container"] = None
        self.sub_stuff["containers"] = []

    def run_once(self):
        super(start_base, self).run_once()
        # 1. Run with no options
        dkrcmd = AsyncDockerCmd(self.parent_subtest, 'start',
                                self.complete_docker_command_line(),
                                self.config['docker_start_timeout'])
        self.loginfo("Executing background command: %s" % dkrcmd)
        dkrcmd.execute()
        while not dkrcmd.done:
            self.loginfo("Starting container...")
            time.sleep(3)
        self.sub_stuff["cmdresult"] = dkrcmd.wait()

    def complete_docker_command_line(self):
        cmds = []

        if self.config["docker_attach"]:
            cmds.append("-a")
        if self.config["docker_interactive"]:
            cmds.append("-i")

        cmds.append(self.sub_stuff["container"].long_id)

        self.sub_stuff["start_cmd"] = cmds

        return cmds

    def outputgood(self):
        # Raise exception if problems found
        OutputGood(self.sub_stuff['cmdresult'])

    def postprocess(self):
        super(start_base, self).postprocess()
        self.outputgood()
        if self.config["docker_expected_result"] == "PASS":
            self.failif(self.sub_stuff['cmdresult'].exit_status != 0,
                        "Non-zero start exit status: %s"
                        % self.sub_stuff['cmdresult'])

        elif self.config["docker_expected_result"] == "FAIL":
            self.failif(self.sub_stuff['cmdresult'].exit_status == 0,
                        "Zero start exit status: Command should fail due to"
                        " wrong command arguments.")

    def cleanup(self):
        super(start_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean

        if (self.config['remove_after_test'] and
                'containers' in self.sub_stuff):
            for cont in self.sub_stuff["containers"]:
                try:
                    cid = cont.long_id
                    self.sub_stuff["conts_obj"].kill_container_by_long_id(cid)
                    self.wait_for_container_death(cont)
                except Exception, e:
                    print e
                self.sub_stuff["conts_obj"].remove_by_obj(cont)

    def wait_for_container_death(self, container_obj):
        cont_id = container_obj.long_id
        prep_changes = DockerCmd(self.parent_subtest, "wait",
                                 [cont_id],
                                 self.config['docker_run_timeout'])

        results = prep_changes.execute()
        return results.exit_status


class short_term_app(start_base):
    config_section = 'docker_cli/start/short_term_app'

    def initialize(self):
        super(short_term_app, self).initialize()

        docker_name = DockerImage.full_name_from_component(
            self.config["docker_repo_name"],
            self.config["docker_repo_tag"])
        # Private to this instance, outside of __init__
        prep_changes = DockerCmd(self.parent_subtest, "run",
                                 ["-d",
                                  docker_name,
                                  self.config["run_cmd"]],
                                 self.config['docker_run_timeout'])

        results = prep_changes.execute()
        if results.exit_status:
            raise error.TestNAError("Problems during initialization of"
                                    " test: %s" % results)
        else:
            cont_id = results.stdout.strip()
            cont = self.sub_stuff["conts_obj"].list_containers_with_cid(cont_id)
            if cont == []:
                raise error.TestNAError("Problems during initialization of"
                                        " test: Failed to find container with"
                                        "id %s." % cont_id)
            self.sub_stuff["container"] = cont[0]
            self.sub_stuff["containers"].append(self.sub_stuff["container"])

        if self.config["check_if_cmd_finished"]:
            self.wait_for_container_death(cont[0])
