"""
Test that mulitple containers can write to the same mounted
volume at the same time.

1. Create 'num_containers' of containers that preform an
   IO command that takes time.
2. Run them simultaneously using the AsyncDockerCmd
3. Assert that they all were able to perform their task
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


from autotest.client import utils
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from run_volumes import volumes_base
import hashlib


class volumes_one_source(volumes_base):

    def initialize(self):
        super(volumes_one_source, self).initialize()
        num_containers = self.config['num_containers']
        commands = []
        self.sub_stuff['names'] = []
        exec_command = self.config['exec_command']
        cntr_path = self.config['cntr_path']
        host_path = self.tmpdir
        vols = ['--volume="%s:%s"' % (host_path, cntr_path)]
        fqin = [DockerImage.full_name_from_defaults(self.config)]
        for _ in range(num_containers):
            name = utils.generate_random_string(12)
            template_keys = {'write_path': cntr_path + "/" + name,
                             'name': name}
            self.sub_stuff['names'] += [name]
            cmd = [exec_command % safe_substitute(template_keys)]
            subargs = ['--name=%s' % (name)] + vols + fqin + cmd
            commands.append(AsyncDockerCmd(self.parent_subtest,
                                           'run',
                                           subargs))
        self.sub_stuff['commands'] = commands

    def run_once(self):
        super(volumes_one_source, self).run_once()
        commands = self.sub_stuff['commands']
        cmd_timeout = self.config['cmd_timeout']
        _ = [x.execute() for x in commands]  # side effects!
        cmdresults = [x.wait(timeout=cmd_timeout) for x in commands]
        self.sub_stuff['cmdresults'] = cmdresults

    def postprocess(self):
        super(volumes_one_source, self).postprocess()
        # assert exit statuses
        for result in self.sub_stuff['cmdresults']:
            self.failif(result.exit_status != 0,
                        "Command: '%s' failed with exit "
                        "status: %s " % (result.command, result.exit_status))
        #assert md5sums
        cntr_md5s = [x.stdout.split()[0] for x in self.sub_stuff['cmdresults']]
        cntr_results = zip(self.sub_stuff['names'], cntr_md5s)
        for name, result in cntr_results:
            file_path = self.tmpdir + "/" + name
            with open(file_path, 'r') as content:
                data = content.read()
                #uncommenting these print lines will show that the files are
                #being written at the same time
                #print file_path
                #print data
            md5 = hashlib.md5(data).hexdigest()
            self.failif(result != md5,
                        "MD5 mismatch for container: %s" % (name))

    def cleanup(self):
        super(volumes_one_source, self).cleanup()
        if self.config['remove_after_test']:
            for name in self.sub_stuff['names']:
                dkrcmd = DockerCmd(self.parent_subtest, 'rm', [name])
                dkrcmd.execute()
