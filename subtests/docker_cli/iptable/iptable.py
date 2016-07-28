r"""
Summary
----------

This a set of test that check the container's iptable rules on host.

Operational Summary
----------------------

#. Run container and parse/gather it's iptable rules on host.
#. Check if rules are affected as expected/are handled properly.

Prerequisites
------------------------------------
*  Docker daemon is running and accessible by it's unix socket.
*  iptables service is **not** running, nor other services which
   change iptables (like libvirtd).
*  Firewalld daemon is running and does not show any errors about
   fail to add rules (https://bugzilla.redhat.com/show_bug.cgi?id=1101484).
*  Command iptable and brctl are working well.
*  sysctl's net.bridge.bridge-nf-call-iptables and -ip6tables are set to 1
"""

from difflib import unified_diff
from autotest.client import utils
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.containers import DockerContainers
from dockertest.config import get_as_list
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCallerSimultaneous


class iptable(SubSubtestCallerSimultaneous):

    pass


class iptable_base(SubSubtest):

    def init_stuff(self):
        self.sub_stuff['subargs'] = None
        self.sub_stuff['name'] = None
        self.sub_stuff['rules_before'] = []
        self.sub_stuff['rules_during'] = []
        self.sub_stuff['rules_after'] = []

    def init_subargs(self):
        """
        Initialize basic arguments that will use for start container
        Will return a list 'args'
        """
        docker_containers = DockerContainers(self)
        image = DockerImage.full_name_from_defaults(self.config)
        name = docker_containers.get_unique_name()
        self.sub_stuff['name'] = name
        bash_cmd = self.config['bash_cmd']
        args = ["--name=%s" % name]
        args += get_as_list(self.config['run_args_csv'])
        args += [image, bash_cmd]
        return args

    def cntnr_ip_map(self):
        """
        Return mapping of container names to IP addresses
        """
        # map container eth0 ifindex's to names
        dc = DockerContainers(self)
        names = dc.list_container_names()
        jsons = [dc.json_by_name(name)[0] for name in names]
        njs = dict(zip(names, jsons))
        result = {}
        for name in [_ for _ in njs
                     if njs[_]["NetworkSettings"]["IPAddress"] != ""]:
            result[name] = njs[name]["NetworkSettings"]["IPAddress"]
            self.logdebug("%s -> %s", name, result[name])
        return result

    @staticmethod
    def read_iptable_rules(ipaddress):
        """
        Find container related iptable rules

        param veth: Container's virtual net card, None for all rules
        """
        iptables_cmd = 'iptables -L -n -v'
        iptables_rules = utils.run(iptables_cmd, verbose=False)
        rules = iptables_rules.stdout.splitlines()
        if ipaddress is None:
            return rules
        return [rule for rule in rules if rule.find(ipaddress) > -1]

    @staticmethod
    def log_diff(method, before, after, header=None):
        if header:
            method(header)
        for line in unified_diff(before, after):
            method(line)

    def initialize(self):
        super(iptable_base, self).initialize()
        self.init_stuff()
        self.sub_stuff['rules_before'] = self.read_iptable_rules(None)
        self.sub_stuff['subargs'] = self.init_subargs()

    def run_once(self):
        super(iptable_base, self).run_once()
        subargs = self.sub_stuff['subargs']
        mustpass(DockerCmd(self, 'run -d', subargs).execute())
        self.sub_stuff['rules_during'] = self.read_iptable_rules(None)

    def postprocess(self):
        super(iptable_base, self).postprocess()
        name = self.sub_stuff['name']
        DockerContainers(self).wait_by_name(name)

        self.sub_stuff['rules_after'] = self.read_iptable_rules(None)

    def cleanup(self):
        super(iptable_base, self).cleanup()
        if self.config['remove_after_test']:
            DockerContainers(self).clean_all([self.sub_stuff['name']])


class iptable_remove(iptable_base):

    """
    Test if container iptable rules are removed after stopped
    """

    def init_stuff(self):
        super(iptable_remove, self).init_stuff()
        self.sub_stuff['cntnr_before'] = set()
        self.sub_stuff['cntnr_during'] = set()

    def initialize(self):
        super(iptable_remove, self).initialize()
        name = self.sub_stuff['name']
        ipaddr = self.cntnr_ip_map().get(name)
        if ipaddr is not None:
            self.loginfo("IP before %s run (bad): %s", name, ipaddr)
            self.sub_stuff['cntnr_before'] = set(
                self.read_iptable_rules(ipaddr))
        else:
            self.loginfo("No IP before %s run (good)", name)

    def run_once(self):
        super(iptable_remove, self).run_once()
        name = self.sub_stuff['name']
        ipaddr = self.cntnr_ip_map().get(name)
        if ipaddr is not None:
            self.logwarning("IP while %s run (good): %s", name, ipaddr)
            self.sub_stuff['cntnr_during'] = set(
                self.read_iptable_rules(ipaddr))
        else:
            self.logwarning("No IP while %s run (bad)", name)
        self.log_diff(self.logdebug,
                      self.sub_stuff['rules_before'],
                      self.sub_stuff['rules_during'],
                      "iptables rule diff before run -> during run")

    def postprocess(self):
        super(iptable_remove, self).postprocess()
        name = self.sub_stuff['name']
        try:
            DockerContainers(self).remove_by_name(name)
        except ValueError:
            pass  # already removed
        cntnr_before = self.sub_stuff['cntnr_before']
        cntnr_during = self.sub_stuff['cntnr_during']
        ipaddr = self.cntnr_ip_map().get(name)
        if ipaddr is not None:
            self.loginfo("IP after %s run (bad): %s", name, ipaddr)
            cntnr_after = set(self.read_iptable_rules(ipaddr))
        else:
            cntnr_after = set()
            self.logwarning("No IP after %s run (good)", name)
        self.log_diff(self.logdebug,
                      self.sub_stuff['rules_during'],
                      self.sub_stuff['rules_after'],
                      "iptables rule diff during run -> after run")
        self.failif(cntnr_before, "Rules found before run")
        self.failif(not cntnr_during, "No rules were added")
        self.failif(cntnr_after & cntnr_during,
                    "Rules left over after removal")
