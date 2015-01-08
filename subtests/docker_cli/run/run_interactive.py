import os
from dockertest.dockercmd import AsyncDockerCmd
from run import run_base


class run_interactive(run_base):

    def init_dockercmd(self):
        in_pipe_r, in_pipe_w = os.pipe()
        self.sub_stuff['stdin'] = in_pipe_r
        self.sub_stuff['stdin_write'] = in_pipe_w
        dkrcmd = AsyncDockerCmd(self, 'run', self.sub_stuff['subargs'])
        self.sub_stuff['dkrcmd'] = dkrcmd

    def run_once(self):
        super(run_interactive, self).run_once()
        # Not needed anymore
        os.close(self.sub_stuff['stdin'])
        # Assume it's line-buffered
        secret_sauce = '%s\n' % self.config['secret_sauce']
        os.write(self.sub_stuff['stdin_write'], secret_sauce)
        # Should cause container to exit
        os.close(self.sub_stuff['stdin_write'])
        self.sub_stuff['dkrcmd'].wait()

    def postprocess(self):
        super(run_interactive, self).postprocess()
        secret_sauce = self.config['secret_sauce']
        dkrcmd = self.sub_stuff['dkrcmd']
        self.failif(dkrcmd.stdout.find(secret_sauce) == -1,
                    "Expected '%s' in output: %s"
                    % (secret_sauce, dkrcmd))
