"""
Test attach

1) Start docker run --interactive --name=xxx fedora cat
2) Start docker attach --no-stdin
3) Try write to stdin using docker run process (should pass)
4) Try write to stdin using docker attach process (shouldn't pass)
5) check if docker run process didn't get input from attach process.
6) check if docker attach/run process got stdin from docker run process.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from attach import simple_base, attach_base
from dockertest.output import OutputGood


class no_stdin(simple_base):
    def postprocess(self):
        super(attach_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected

        OutputGood(self.sub_stuff['cmdresult'])

        str_run_cmd_output = self.config["check_run_cmd_out"]
        str_attach_cmd_output = self.config["check_attach_cmd_out"]
        cmd_stdout = self.sub_stuff['cmd_run'].stdout
        cmd_stdout_attach = self.sub_stuff['cmd_attach'].stdout

        self.failif(str_run_cmd_output not in cmd_stdout,
                    "Command %s output must contain %s but doesn't."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_run_cmd_output,
                         self.sub_stuff['cmdresult']))

        self.failif(str_attach_cmd_output in cmd_stdout,
                    "Command %s output must not contain %s."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_attach_cmd_output,
                         self.sub_stuff['cmdresult']))

        self.failif(str_run_cmd_output not in cmd_stdout_attach,
                    "Command %s output must contain %s but doesn't."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_run_cmd_output,
                         self.sub_stuff['cmdresult_attach']))

        self.failif(str_attach_cmd_output in cmd_stdout_attach,
                    "Command %s output must not contain %s."
                    " Detail:%s" %
                        (self.config["bash_cmd"],
                         str_attach_cmd_output,
                         self.sub_stuff['cmdresult_attach']))
