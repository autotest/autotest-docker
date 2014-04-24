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
from run_simple import run_base


class run_remote_tag(run_base):

    def initialize(self):
        super(run_remote_tag, self).initialize()
        rand_name = utils.generate_random_string(8).lower()
        self.sub_stuff["rand_name"] = rand_name
        self.sub_stuff["subargs"] = []
        self.sub_stuff["subargs"].append("--name=%s " % (rand_name))
        self.sub_stuff["subargs"].append(self.config["missing_remote_tag"])
        self.sub_stuff["subargs"].append(self.config["bash_cmd"])

        remote_image = self.config["missing_remote_tag"]
        images = self.sub_stuff["img"].list_imgs_with_full_name(remote_image)
        if images != []:
            error.TestNAError("Unable to prepare env for test:"
                              " image with name missing_remote_tag already"
                              " exist in docker")

        self.sub_stuff["images"].append(self.config["missing_remote_tag"])

    def run_command(self, cmd, subargs, cmd_name):
        dkrcmd = DockerCmd(self.parent_subtest, cmd, subargs,
                           timeout=self.config['docker_timeout'])
        dkrcmd.verbose = True

        self.sub_stuff[cmd_name] = dkrcmd.execute()
        return self.sub_stuff[cmd_name]

    def run_once(self):
        self.loginfo("Starting background docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        out = self.run_command('run', self.sub_stuff['subargs'],
                               'cmdresult_run1')
        if out.exit_status != 0:
            return

        out = self.run_command('rm', [self.sub_stuff["rand_name"]],
                               'cmdresult_rm')
        if out.exit_status != 0:
            return

        out = self.run_command('tag',
                               [self.config["missing_remote_tag"],
                                self.sub_stuff["rand_name"]],
                               'cmdresult_tag')
        if out.exit_status != 0:
            return

        self.sub_stuff["images"].append(self.sub_stuff["rand_name"])

        out = self.run_command('rmi',
                               [self.config["missing_remote_tag"]],
                               'cmdresult_rmi')
        if out.exit_status != 0:
            return

        out = self.run_command('run', self.sub_stuff['subargs'],
                               'cmdresult_run2')
        if out.exit_status != 0:
            return
        self.sub_stuff["containers"].append(self.sub_stuff["rand_name"])

    def postprocess(self):
        super(run_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        OutputGood(self.sub_stuff['cmdresult_run1'])
        OutputGood(self.sub_stuff['cmdresult_tag'])
        OutputGood(self.sub_stuff['cmdresult_rmi'])
        OutputGood(self.sub_stuff['cmdresult_run2'])

        cmd_run1 = self.sub_stuff['cmdresult_run1']
        cmd_tag = self.sub_stuff['cmdresult_tag']
        cmd_rmi = self.sub_stuff['cmdresult_rmi']
        cmd_run2 = self.sub_stuff['cmdresult_run2']

        self.failif(cmd_run1.exit_status != 0,
                    "Problem with run1 cmd detail :%s" %
                    cmd_run1)

        self.failif(cmd_tag.exit_status != 0,
                    "Problem with tag cmd detail :%s" %
                    cmd_tag)

        self.failif(cmd_rmi.exit_status != 0,
                    "Problem with rmi cmd detail :%s" %
                    cmd_rmi)

        self.failif(cmd_run2.exit_status != 0,
                    "Problem with run2 cmd detail :%s" %
                    cmd_run2)

        self.failif("Pulling fs layer" in cmd_run2.stderr,
                    "Image was downloaded even if images with same id was in"
                    " local repository.")

        img_name = self.sub_stuff["rand_name"]
        images = self.sub_stuff["img"].list_imgs_with_full_name(img_name)
        self.failif(images == [], "Unable to find loaded image.")
