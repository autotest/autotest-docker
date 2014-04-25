"""
Test run

1) Start docker run --interactive --attach=stdout --name=xxx fedora cat
2) Start docker attach xxx
3) Try write to stdin using docker run process (shouldn't pass)
4) Try write to stdin using docker attach process (should pass)
5) check if docker run process get input from attach process.
6) check if docker attach/run process don't get stdin from docker run process.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from autotest.client.shared import error
from autotest.client import utils
from dockertest.dockercmd import DockerCmd
from dockertest.output import OutputGood
from dockertest.images import DockerImages
from dockertest.containers import DockerContainers
from run_simple import run_base

class run_remote_tag(run_base):

    def initialize(self):
        super(run_remote_tag, self).initialize()
        dc = DockerContainers(self.parent_subtest)
        rand_name = dc.get_unique_name()
        self.sub_stuff["rand_name"] = rand_name
        self.sub_stuff["subargs"].insert(0, "--name=%s " % rand_name)

    def run_command(self, cmd, subargs, cmd_name):
        dkrcmd = DockerCmd(self.parent_subtest, cmd, subargs,
                           timeout=self.config['docker_timeout'])
        self.loginfo(dkrcmd.command)
        result = dkrcmd.execute()
        self.sub_stuff[cmd_name] = result
        self.logdebug("Command %s: %s" % (cmd_name, result))

    def run_once(self):
        fqin = self.sub_stuff['fqin']
        di = DockerImages(self.parent_subtest)
        try:
            di.remove_image_by_full_name(fqin)
        except error.CmdError:
            pass  # removal was the goal
        images = di.list_imgs_with_full_name(fqin)
        if images != []:
            error.TestNAError("Unable to prepare env for test:"
                              " image %s already/still"
                              " exist in docker repository", fqin)

        self.logdebug("Existing images: %s", di.list_imgs_full_name())
        self.loginfo("Executing test commands")

        self.run_command('run', self.sub_stuff['subargs'],
                         'cmdresult_run1')

        self.run_command('rm', [self.sub_stuff["rand_name"]],
                         'cmdresult_rm')

        self.run_command('tag',
                         [fqin, self.sub_stuff["rand_name"].lower()],
                         'cmdresult_tag')

        self.run_command('rmi',
                         [fqin],
                         'cmdresult_rmi')

        self.run_command('run', self.sub_stuff['subargs'],
                         'cmdresult_run2')

        self.run_command('rm', [self.sub_stuff["rand_name"]],
                         'cmdresult_rm2')

        self.run_command('rmi',
                         [self.sub_stuff["rand_name"].lower()],
                         'cmdresult_rmi2')

    def postprocess(self):
        super(run_remote_tag, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        cmdresults = {}
        for name in ['cmdresult_run1', 'cmdresult_rm',
                     'cmdresult_tag', 'cmdresult_rmi',
                     'cmdresult_rmi2', 'cmdresult_run2',
                     'cmdresult_rm2']:
            try:
                cmdresults[name] = self.sub_stuff[name]
            except KeyError:
                self.logerror("A command %s did not run, prior cmdresults: %s"
                              % (name, cmdresults))
                raise

        for name, cmdresult in cmdresults.items():
            OutputGood(cmdresult)
            self.failif(cmdresult.exit_status != 0,
                        "Problem with %s command: %s"
                        % (name, cmdresult))

        self.failif(cmdresults['cmdresult_run2'].stderr.count("ling fs ") != 0,
                    "Image was downloaded even if images with same id was in"
                    " local repository: %s" % cmdresults['cmdresult_run2'])
