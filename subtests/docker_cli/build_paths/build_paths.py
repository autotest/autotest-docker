"""
Simple test that builds a given docker path or git repo using
the ``docker build`` command

1. Iterate through each build path in config
2. Check for errors
"""

from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImages, DockerImage
from dockertest.output import OutputGood
from dockertest.subtest import Subtest
from dockertest.xceptions import DockerTestNAError
import os.path
import re
import shutil

class build_paths(Subtest):

    def _init_build_paths(self):
        paths = self.config['build_paths'].strip().split(',')
        self.stuff['build_paths'] = []
        for p in paths:
            # full paths or git locations
            if p.startswith('/') or p.endswith('.git'):
                self.stuff['build_paths'].append(p)
            # else determine relative paths
            else:
                dpath = os.path.join(self.bindir, p)
                if not os.path.isdir(dpath):
                    msg = "%s is not a valid directory." % (dpath)
                    raise DockerTestNAError(msg)
                dfile = os.path.join(dpath, 'Dockerfile')
                if not os.path.isfile(dfile):
                    msg = "%s does not contain a Dockerfile." % (dpath)
                    raise DockerTestNAError(msg)
                dpath = self._set_dockerfile_from(p)
                self.stuff['build_paths'].append(dpath)
        self.iterations = len(paths)

    @staticmethod
    def _copy_directory(src, dest):
        try:
            shutil.copytree(src, dest)
        # Directories are the same
        except shutil.Error as e:
            print 'Could not sandbox docker build path. Error: %s' % (e)
        # Any error saying that the directory doesn't exist
        except OSError as e:
            print 'Could not sandbox docker build path. Error: %s' % (e)

    def _set_dockerfile_from(self, folder):
        src = os.path.join(self.bindir, folder)
        dest = os.path.join(self.tmpdir, folder)
        self._copy_directory(src, dest)
        dfile = os.path.join(dest, 'Dockerfile')
        image = DockerImage.full_name_from_defaults(self.config)
        with open(dfile, 'r') as dockerfile:
            lines = dockerfile.readlines()
        with open(dfile, 'w') as dockerfile:
            re_search = r'^(?i)FROM.*'
            re_replace = 'FROM ' + image
            for line in lines:
                out = re.sub(re_search, re_replace, line)
                dockerfile.write(out)
        return dest

    def _init_build_args(self):
        self.stuff['gen_tag'] = True
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

    def initialize(self):
        super(build_paths, self).initialize()
        self._init_build_paths()

        # determine iterations
        self.iterations = len(self.stuff['build_paths'])
        self.stuff['passed'] = [False for _ in xrange(self.iterations)]

        self._init_build_args()
        #stuff needed later
        self.stuff['names'] = []
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
        self.logoutput(cmdresult)
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
        # https://bugzilla.redhat.com/show_bug.cgi?id=1097884
        if self.config['try_remove_after_test']:
            dkrcmd = DockerCmd(self, 'rmi', self.stuff['names'])
            res = dkrcmd.execute()
            self.logoutput(res)
            testr = res.exit_status != 0 or "Error:" in res.stderr
            self.failif(testr, "Errors during removal of images.")

    def logoutput(self, result):
        self.loginfo("Exit: '%s'", result.exit_status)
        self.logdebug("Stdout: '%s'", result.stdout)
        self.logdebug("Stderr: '%s'", result.stderr)

    def cleanup(self):
        super(build_paths, self).cleanup()
        # same as the postprocess rmi, but with --force
        if self.config['remove_after_test']:
            dkrcmd = DockerCmd(self, 'rmi', ['-f'] + self.stuff['names'])
            dkrcmd.execute()
