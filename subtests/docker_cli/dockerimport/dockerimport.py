"""
Based on config['test_subsection_postfixes'] load module, call function.
"""

import sys, imp, os.path
from autotest.client.shared import error
from dockertest import subtest

class dockerimport(subtest.Subtest):
    version = "0.0.1"  #  Used to track when setup() should run
    config_section = 'docker_cli/dockerimport'

    def initialize(self):
        super(dockerimport, self).initialize()
        # Private to this instance, outside of __init__
        start_subsubtests = self.config['start_subsubtests'] = {}
        run_subsubtests = self.config['run_subsubtests'] = {}
        for name in self.config['test_subsubtest_postfixes'].split(','):
            subsubtest = self.new_subsubtest(name)
            if subsubtest is not None:
                # Guarantee it's cleanup() runs
                start_subsubtests[name] = subsubtest
                try:
                    subsubtest.initialize()
                    # Allow run_once()
                    run_subsubtests[name] = subsubtest
                except Exception, detail:
                    # Log problem, don't add to run_subsubtests
                    self.logerror("%s failed to initialize: %s: %s", name,
                                  detail.__class__.__name__, detail)

    def run_once(self):
        super(dockerimport, self).run_once()
        post_subsubtests = self.config['post_subsubtests'] = {}
        for name, subsubtest in self.config['run_subsubtests'].items():
            try:
                subsubtest.run_once()
                # Allow postprocess()
                post_subsubtests[name] = subsubtest
            except Exception, detail:
                # Log problem, don't add to post_subsubtests
                self.loginfo("%s failed in run_once: %s: %s", name,
                             detail.__class__.__name__, detail)

    def postprocess(self):
        super(dockerimport, self).postprocess()
        # Dictionary is overkill for pass/fail determination
        start_subsubtests = set(self.config['start_subsubtests'].keys())
        final_subsubtests = set()
        for name, subsubtest in self.config['post_subsubtests'].items():
            try:
                subsubtest.postprocess()
                # Will form "passed" set
                final_subsubtests.add(name)
            # Fixme: How can this be avoided, yet guarantee cleanup() and
            #        postprocess for other subtests?
            except Exception, detail:
                # Forms "failed" set by exclusion, but log problem
                self.loginfo("%s failed in postprocess: %s: %s", name,
                             detail.__class__.__name__, detail)
        if not final_subsubtests == start_subsubtests:
            raise error.TestFail('Sub-subtest failures: %s'
                                 % str(start_subsubtests - final_subsubtests))

    def cleanup(self):
        super(dockerimport, self).cleanup()
        cleanup_failures = set()
        for name, subsubtest in self.config['start_subsubtests'].items():
            try:
                subsubtest.cleanup()
            except Exception, detail:
                cleanup_failures.add(name)
                self.logerror("%s failed to cleanup: %s: %s", name,
                              detail.__class__.__name__, detail)
        if len(cleanup_failures) > 0:
            raise error.TestError("Sub-subtest cleanup failures: %s"
                                   % cleanup_failures)

    def new_subsubtest(self, name):
        try:
            mydir = self.bindir
            mod = imp.load_module(name, *imp.find_module(name, [mydir]))
            cls = getattr(mod, name, None)
            if callable(cls):
                return cls(self)
        except (ImportError, OSError, AttributeError, TypeError), detail:
            self.logwarning("Ignorning sub-subtest %s import exception %s: %s",
                            name, detail.__class__.__name__, detail)
            # So they can be skipped
            return None
