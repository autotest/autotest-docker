from run import run_base
from dockertest.dockercmd import DockerCmd
from dockertest.output import OutputGood
from dockertest.output import mustpass


class run_attach_stdout(run_base):

    def initialize(self):
        super(run_attach_stdout, self).initialize()
        attachcmd = DockerCmd(self, 'attach', [self.sub_stuff['name']])
        self.sub_stuff['attachcmd'] = attachcmd

    def run_once(self):
        super(run_attach_stdout, self).run_once()
        # Assumes dkrcmd.execute() returns immediatly once container running
        self.sub_stuff['attachcmd'].execute()

    def postprocess(self):
        super(run_attach_stdout, self).postprocess()
        attach_cmdresult = self.sub_stuff['attachcmd'].cmdresult
        OutputGood(attach_cmdresult, skip=['nonprintables_check'])
        mustpass(attach_cmdresult)
        secret_sauce = self.config['secret_sauce']
        secret_present = attach_cmdresult.stdout.find(secret_sauce) != -1
        self.failif(not secret_present,
                    "Test data not found from attach command output: %s"
                    % attach_cmdresult)
