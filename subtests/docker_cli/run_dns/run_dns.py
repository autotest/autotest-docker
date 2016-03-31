"""
Summary
-------

Set various dns' and dns-searches and check docker behave well.

Operational Summary
---------------------

#.  Execute couple of correctly set dns/dns-search scenarios
#.  Execute couple of incorrect dns/dns-search scenarios
"""
import random
import re

from autotest.client import utils
from dockertest import subtest
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass, mustfail
from dockertest.images import DockerImage
import itertools


class run_dns(subtest.Subtest):

    """
    Test body
    """
    re_nameserver = re.compile(r'nameserver (.*)')
    re_search = re.compile(r'search (.*)')

    def _execute_bad(self, dns, search):
        """ Execute and expect failure """
        subargs = self.stuff['subargs'][:]
        if dns:
            for server in dns:
                subargs.insert(0, '--dns %s' % server)
        if search:
            for name in search:
                subargs.insert(0, '--dns-search %s' % name)
        return mustfail(DockerCmd(self, 'run', subargs,
                                  verbose=False).execute(), 125)

    def _execute_and_record(self, dns, search, dnss, searches):
        """ Execute and store the new dns/searches """
        subargs = self.stuff['subargs'][:]
        if dns:
            for server in dns:
                subargs.insert(0, '--dns %s' % server)
        if search:
            for name in search:
                subargs.insert(0, '--dns-search %s' % name)
        res = mustpass(DockerCmd(self, 'run', subargs,
                                 verbose=False).execute())
        dnss.append(self.re_nameserver.findall(res.stdout))
        search = self.re_search.findall(res.stdout)
        self.failif(len(search) > 1, "Number of search lines is > 1:\n%s"
                    % res)
        if search:
            search = search[0].split(' ')
        searches.append(search)

    @staticmethod
    def _ieq(first, second):
        """ Iterables equal - compares iterables using set """
        return set(first) == set(second)

    def run_once(self):
        super(run_dns, self).run_once()
        fin = DockerImage.full_name_from_defaults(self.config)
        self.stuff['subargs'] = ['--privileged', '--rm', fin,
                                 "cat /etc/resolv.conf"]
        self.test_good()
        self.test_bad()

    def test_good(self):
        """ Set couple of dns'/searches variants and verify them """
        dnss = []
        searches = []
        # Default dns/search
        self._execute_and_record(None, None, dnss, searches)
        # Change only dns
        dns = [self.generate_ipaddr(dnss)]
        self._execute_and_record(dns, None, dnss, searches)
        self.failif(not self._ieq(dnss[-1], dns), "Dns was set to %s but "
                    "in /etc/resolv.conf it's %s" % (dns, dnss[-1]))
        self.failif(not self._ieq(searches[-1], searches[0]), "Search was not "
                    "set so it should be as in ref run %s but is %s instead."
                    % (searches[0], searches[-1]))
        # Change only seach
        search = [self.generate_search("example.", searches)]
        self._execute_and_record(None, search, dnss, searches)
        self.failif(not self._ieq(dnss[-1], dnss[0]), "Dns was not "
                    "set so it should be as in ref run %s but is %s instead."
                    % (dnss[0], dnss[-1]))
        self.failif(not self._ieq(searches[-1], search), "Search was set to "
                    "%s but is %s instead" % (search, searches[-1]))
        # Change booth
        dns = [self.generate_ipaddr(dnss)]
        search = [self.generate_search("example.", searches)]
        self._execute_and_record(dns, search, dnss, searches)
        self.failif(not self._ieq(dnss[-1], dns), "Dns was set to %s but in "
                    "/etc/resolv.conf it's %s" % (dns, dnss[-1]))
        self.failif(not self._ieq(searches[-1], search), "Search was set to %s"
                    " but is %s instead" % (search, searches[-1]))
        # Multiple dnss and searches
        dns = [self.generate_ipaddr(dnss) for _ in xrange(5)]
        search = [self.generate_search("example.", searches)
                  for _ in xrange(5)]
        self._execute_and_record(dns, search, dnss, searches)
        self.failif(not self._ieq(dnss[-1], dns), "Dns was set to %s but in "
                    "/etc/resolv.conf it's %s" % (dns, dnss[-1]))
        self.failif(not self._ieq(searches[-1], search), "Search was set to %s"
                    " but is %s instead" % (search, searches[-1]))

    def test_bad(self):
        """ Set couple of wrong dns'/searches and verify it fails """
        for bad_dns in ("bad.dns", "256.0.0.1", "1.1.1.256", "19216801",
                        "4.2.2.1.1"):
            self._execute_bad([bad_dns], None)
        for bad_search in ("bad search", "-example", "exam..ple", 'X' * 300):
            self._execute_bad(None, [bad_search])

    def generate_ipaddr(self, mask=None):
        """ Generate ip addres in range <0-255> not present in mask """
        for _ in xrange(1000):
            addr = '.'.join((str(random.randrange(256)) for _ in xrange(4)))
            if mask and addr in itertools.chain.from_iterable(mask):
                continue
            break
        else:
            self.failif(True, "Unable to generate IP addr in 1000 iterations. "
                        "(%s)" % mask)
        return addr

    def generate_search(self, prefix, mask=None):
        """ Generate string not present in mask """
        for _ in xrange(1000):
            search = prefix + utils.generate_random_string(6)
            if mask and search in itertools.chain.from_iterable(mask):
                continue
            break
        else:
            self.failif(True, "Unable to generate search in 1000 iterations. "
                        "(%s, %s)" % (prefix, mask))
        return search
