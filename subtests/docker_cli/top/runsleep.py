from top import base
from dockertest.dockercmd import DockerCmd
from dockertest.output import OutputGood
from dockertest.output import TextTable
import dockertest.docker_daemon as docker_daemon


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
        OutputGood(self.sub_stuff['run_dkrcmd'].cmdresult,
                   skip=['nonprintables_check'])
        OutputGood(self.sub_stuff['top_dkrcmd'].cmdresult)
        pstable = TextTable(self.sub_stuff['top_dkrcmd'].stdout)
        self.failif_ne(len(pstable), 1, "Number of rows returned by top")
        psrow = pstable[0]
        self.failif_ne(psrow['USER'], self._expected_user(), 'Expected user')
        self.failif(int(psrow['PID']) == 1, 'Process PID is 1')
        self.failif_ne(psrow['COMMAND'], self.COMMAND, 'Expected command')

    @staticmethod
    def _expected_user():
        """
        Most of the time, we expect root. When running with user namespaces
        enabled, docker uses the subordinate uid specified for 'dockremap'
        in the file /etc/subuid.
        """
        if docker_daemon.user_namespaces_enabled():
            return str(docker_daemon.user_namespaces_uid())

        # The usual case: no userns
        return 'root'
