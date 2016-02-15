r"""
Summary
---------

This subtest checks functionality of varios environment variable related
options / operations of docker.


Operational Summary
----------------------

#. Run container with various environment-var related options.
#. Verify healthy container exit state/status.
#. Verfiy container environment variables match expectations.


Operational Detail
-------------------

"spam" sub-subtest:

#. Generate hundreds of random short-named env. vars with short values
   (so as to not exceede max command-line length)
#. Execute docker run command with -e options for list, volume mounting
   the sub-subtest's results dir into the container.
#. Dump out container env into a file in mounted results dir
#. Verify healthy container exit, no oopses or non-zero exit codes
#. Verify generated environment vars match number & content in dump file.
#. Ignore any container environment variables that don't contain a special
   identifying prefix/suffix.
"""

import os
import os.path
import shutil
from dockertest.subtest import SubSubtestCaller
from dockertest.subtest import SubSubtest
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImages
from dockertest.output import mustpass


class run_env(SubSubtestCaller):
    pass


class spam(SubSubtest):

    # Allows quickly rejecting container env. supplied vars
    KEYPFX = '_x'
    VALPFX = 'x_'

    @property
    def test_dict(self):
        howmany = self.config['n_env']
        keyfmt = "%s%%x" % self.KEYPFX
        valfmt = "%s%%x" % self.VALPFX
        keyiter = (keyfmt % x for x in xrange(0, howmany))
        valiter = (valfmt % x for x in xrange(howmany, 0, -1))
        return dict(zip(keyiter, valiter))

    def save_testdata(self):
        self.sub_stuff['output'] = os.path.join(self.tmpdir, 'env.output')
        resultdir = self.parent_subtest.resultsdir
        inputcopy = os.path.join(resultdir, "env.input")
        with open(inputcopy, 'wb') as inpf:
            for key, value in self.sub_stuff['envd'].iteritems():
                inpf.write("%s=%s\n" % (key, value))

    def initialize_cmdline(self):
        subargs = ['--rm', '-v', '%s:/x:Z' % self.tmpdir]
        for key, value in self.sub_stuff['envd'].iteritems():
            subargs.append("-e")
            subargs.append("%s=%s" % (key, value))
        subargs.append(DockerImages(self).default_image)
        subargs.append("bash -c 'env > /x/env.output'")
        _ = DockerCmd(self, 'run', subargs, verbose=False)
        _.quiet = True
        self.sub_stuff['dkrcmd'] = _

    def retrieve_testdata(self):
        self.failif(not os.path.isfile(self.sub_stuff['output']),
                    "Could not find %s" % self.sub_stuff['output'])
        resultdir = self.parent_subtest.resultsdir
        outputcopy = os.path.join(resultdir,
                                  os.path.basename(self.sub_stuff['output']))
        shutil.copyfile(self.sub_stuff['output'], outputcopy)
        output = {}
        extra = {}
        with open(self.sub_stuff['output'], "r") as outf:
            for line in outf:
                key, value = line.split('=', 2)
                key = key.strip()
                value = value.strip()
                if (not key.startswith(self.KEYPFX) or
                        not value.startswith(self.VALPFX)):
                    # These are not the droids we're looking for
                    extra[key] = value
                    continue

                output[key] = value

        self.logdebug("Environment variables NOT included in test: %s", extra)
        return output

    def validate_testdata(self, expected, actual, loop_actual=True):
        if loop_actual:
            iterator = actual.iteritems()
            compareto = expected
            name = "input"
        else:
            iterator = expected.iteritems()
            compareto = actual
            name = "output"
        # More helpful to debugging if done this way
        for key, value in iterator:
            if key not in compareto:
                self.logwarning("var %s not found in %s dictionary",
                                key, name)
            if value != compareto[key]:
                self.logwarning("var %s value %s does not match %s's %s",
                                value, key, name, compareto[key])

    def initialize(self):
        super(spam, self).initialize()
        self.sub_stuff['envd'] = self.test_dict
        self.sub_stuff['actual'] = {}
        self.save_testdata()
        self.initialize_cmdline()

    def run_once(self):
        super(spam, self).run_once()
        self.sub_stuff['dkrcmd'].execute()

    def postprocess(self):
        super(spam, self).postprocess()
        mustpass(self.sub_stuff['dkrcmd'].cmdresult)
        expected = self.sub_stuff['envd']
        actual = self.retrieve_testdata()
        for loop_actual in (True, False):
            self.validate_testdata(expected, actual, loop_actual)
