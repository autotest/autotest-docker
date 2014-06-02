"""
Simple test that builds a given docker path or git repo using
the ``docker build`` command

1. Iterate through each build path in config
2. Check for errors
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImages
from dockertest.subtest import Subtest
from dockertest.output import OutputGood
from dockertest.xceptions import DockerTestNAError

class build_paths(Subtest):

    def initialize(self):
        super(build_paths, self).initialize()
        _build_paths = self.config['build_paths'].strip().split(',')
        self.stuff['build_paths'] = _build_paths
        self.iterations = len(_build_paths)
        self.stuff['passed'] = [False for _ in xrange(self.iterations)]
        self.stuff['gen_tag'] = True
        self.stuff['names'] = []
        build_args = self.config['build_args'].strip()
        if '--tag' in build_args or '-t' in build_args:
            if self.iterations > 1:
                raise DockerTestNAError("Cannot apply --tag to"
                                        " more than one image.")
            self.stuff['gen_tag'] = False
            args = build_args.split()
            item = [x for x in args if '--tag' in x or '-t' in x]
            item = item.pop()
            if '=' in item:
                self.stuff['names'].append(item.split('=').pop())
            else:
                self.stuff['names'].append(args.index(item) + 1)
        self.stuff['build_args'] = build_args.split()
        self.stuff['cmdresults'] = []

    def gen_tag(self):
        reponame = self.config['image_repo_name']
        postfix = self.config['image_tag_postfix']
        di = DockerImages(self)
        tag = '%s:%s' % (reponame, di.get_unique_name(suffix=postfix))
        tag = tag.lower()
        self.stuff['names'].append(tag)
        return tag

    def run_once(self):
        super(build_paths, self).run_once()
        build_path = self.stuff['build_paths'][self.iteration - 1]
        subargs = self.stuff['build_args']
        if self.stuff['gen_tag']:
            subargs = subargs + ['--tag=' + self.gen_tag()]
        subargs = subargs + [build_path]
        dkrcmd = DockerCmd(self, 'build', subargs)
        self.stuff['cmdresults'].append(dkrcmd.execute())

    def postprocess_iteration(self):
        super(build_paths, self).postprocess_iteration()
        iter_index = self.iteration - 1
        cmdresult = self.stuff['cmdresults'][iter_index]
        self.loginfo("Exit: '%s'", cmdresult.exit_status)
        self.logdebug("Stdout: '%s'", cmdresult.stdout)
        self.logdebug("Stderr: '%s'", cmdresult.stderr)
        og_true = OutputGood(cmdresult, ignore_error=True)
        if cmdresult.exit_status == 0 and og_true:
            # initialized False by default
            self.stuff['passed'][iter_index] = True
        self.logdebug("Output check: '%s'", str(og_true))

    def postprocess(self):
        super(build_paths, self).postprocess()
        self.failif(not all(self.stuff['passed']),
                    "One or more builds returned non-zero exit status or "
                    "contained erroronious output. See debug log for details.")


    def cleanup(self):
        super(build_paths, self).cleanup()
        if self.config['remove_after_test']:
            dkrcmd = DockerCmd(self, 'rmi', self.stuff['names'])
            dkrcmd.execute()
