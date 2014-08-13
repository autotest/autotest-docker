"""
Test if docker uses local copy image even if tag is different.

1) Remove remote_image_fqin from local repo.
2) Start docker run --name=xxx remote_image_fqin cat
3) Tag image with new local name to keep image id in local repo
4) Remote image tag remote_image_fqin from local repo.
5) Try to Start docker run --name=xxx remote_image_fqin cat and
   check if docker using local copy of image or
   remote copy of image was downloaded  again.
6) Totally remove remote image from local repo.
"""

from autotest.client.shared import error
from dockertest.dockercmd import DockerCmd
from dockertest.output import OutputGood
from dockertest.images import DockerImages, DockerImage
from dockertest.containers import DockerContainers
from run import run_base


class run_remote_tag(run_base):

    def initialize(self):
        if self.config["remote_image_fqin"] == "":
            raise error.TestNAError("Unable to prepare env for test:"
                                    "run_remote_tag/remote_image_fqin have to "
                                    "be filled by functional repo address.")
        comp = DockerImage.split_to_component(self.config["remote_image_fqin"])
        (self.config["docker_repo_name"],
         self.config["docker_repo_tag"],
         self.config["docker_registry_host"],
         self.config["docker_registry_user"]) = comp

        super(run_remote_tag, self).initialize()

        dc = DockerContainers(self.parent_subtest)
        rand_name = dc.get_unique_name()
        self.sub_stuff["rand_name"] = rand_name
        self.sub_stuff["subargs"].insert(0, "--name=%s " % rand_name)

    def run_command(self, cmd, subargs, cmd_name):
        dkrcmd = DockerCmd(self, cmd, subargs,
                           timeout=self.config['docker_timeout'])
        self.loginfo(dkrcmd.command)
        dkrcmd.execute()
        self.sub_stuff[cmd_name] = dkrcmd
        self.logdebug("Command %s: %s" % (cmd_name, dkrcmd.cmdresult))

    def run_once(self):
        fqin = self.sub_stuff['fqin']
        self.sub_stuff["images"].append(fqin)
        di = DockerImages(self.parent_subtest)
        try:
            images = di.list_imgs_with_full_name(fqin)
            for i in images:
                di.remove_image_by_id(i.long_id)
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
                cmdresults[name] = self.sub_stuff[name].cmdresult
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
