from top import base
from dockertest.dockercmd import DockerCmd
from dockertest.output import OutputGood
from dockertest.output import TextTable


class runsleep(base):

    COMMAND = 'sleep 5m'

    def init_run_dkrcmd(self):
        subargs = self.sub_stuff['run_options']
        subargs += [self.sub_stuff['fqin'], self.COMMAND]
        return DockerCmd(self, 'run', subargs)

    def init_top_dkrcmd(self):
        subargs = [self.get_run_name()]
        subargs += self.sub_stuff['top_options']
        return DockerCmd(self, 'top', subargs)

    def get_run_name(self):
        if self.sub_stuff.get('_name') is None:
            dc = self.sub_stuff['dc']
            name = dc.get_unique_name()
            self.sub_stuff['_name'] = name
        return self.sub_stuff.get('_name')

    def run_once(self):
        super(runsleep, self).run_once()
        self.sub_stuff['top_dkrcmd'].execute()  # blocking

    def postprocess(self):
        OutputGood(self.sub_stuff['run_dkrcmd'].cmdresult)
        OutputGood(self.sub_stuff['top_dkrcmd'].cmdresult)
        pstable = TextTable(self.sub_stuff['top_dkrcmd'].stdout)
        self.failif_ne(len(pstable), 1)
        psrow = pstable[0]
        self.failif_ne(psrow['USER'], 'root')
        self.failif(int(psrow['PID']) == 1)
        self.failif_ne(psrow['COMMAND'], self.COMMAND)
