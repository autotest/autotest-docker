"""
Test attach

1) Start docker run --interactive --name=xxx fedora cat
2) Start docker attach --no-stdin
3) Try write to stdin using docker run process (should pass)
4) Try write to stdin using docker attach process (shouldn't pass)
5) check if docker run process didn't get input from attach process.
6) check if docker attach/run process got stdin from docker run process.
"""

from attach import simple_base


class no_stdin(simple_base):

    def verify_output(self):
        # e.g. "append_data"
        check_for = self.config["check_attach_cmd_out"]
        in_output = self.sub_stuff['cmd_run'].stdout
        details = self.sub_stuff['cmdresult']
        self.failif_contain(check_for, in_output, details)

        in_output = self.sub_stuff['cmd_attach'].stdout
        details = self.sub_stuff['cmdresult_attach']
        self.failif_contain(check_for, in_output, details)

        # e.g. "run_data"
        check_for = self.config["check_run_cmd_out"]
        in_output = self.sub_stuff['cmd_run'].stdout
        details = self.sub_stuff['cmdresult']
        self.failif_not_contain(check_for, in_output, details)

        in_output = self.sub_stuff['cmd_attach'].stdout
        details = self.sub_stuff['cmdresult_attach']
        self.failif_not_contain(check_for, in_output, details)
