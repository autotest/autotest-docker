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
"""

from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.containers import DockerContainers
from dockertest.config import get_as_list
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCallerSimultaneous
from autotest.client import utils
import re


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

    def cntnr_veth_map(self):
        """
        Return mapping of container names to veth* devices
        """
        # map ifindex's to ``veth*`` names on host
        tmp_cmd = 'brctl show'
        cmd_result = utils.run(tmp_cmd, verbose=False)
        veths = re.findall(r'veth\w+', cmd_result.stdout)
        ifindex = [int(open('/sys/class/net/%s/ifindex' % veth, 'r').read())
                   for veth in veths]
        index_host = dict(zip(ifindex, veths))
        self.logdebug("Host index to veth: %s", index_host)

        # map container eth0 ifindex's to names
        dc = DockerContainers(self)
        names = dc.list_container_names()
        jsons = [dc.json_by_name(name)[0] for name in names]
        njs = dict(zip(names, jsons))
        result = {}
        for name in [_name for (_name, json) in njs.iteritems()
                     if json["NetworkSettings"]["MacAddress"] != ""]:
            subargs = [name, 'cat', '/sys/class/net/eth0/ifindex']
            dkrcmd = DockerCmd(self, 'exec', subargs, verbose=False)
            dkrcmd.execute()
            if dkrcmd.exit_status == 0:
                # Host's ifindex always one greater than container's
                ifindex = int(dkrcmd.stdout) + 1
                # State could have changed during looping
                if ifindex in index_host:
                    result[name] = index_host[ifindex]
                else:
                    self.logdebug("Host veth %s dissapeared while mapping %s",
                                  ifindex, name)
            else:
                self.logdebug("Can't examine eth0 for container %s", name)
        self.logdebug("Container names to veth: %s", result)
        return result

    @staticmethod
    def read_iptable_rules(veth):
        """
        Find container related iptable rules

        param veth: Container's virtual net card, None for all rules
        """
        iptables_cmd = 'iptables -L -n -v'
        iptables_rules = utils.run(iptables_cmd, verbose=False)
        rules = iptables_rules.stdout.splitlines()
        if veth is None:
            return rules
        return [rule for rule in rules if rule.find(veth) > -1]

    def initialize(self):
        super(iptable_base, self).initialize()
        self.init_stuff()
        self.sub_stuff['rules_before'] = self.read_iptable_rules(None)
        self.logdebug("Rules before:\n%s",
                      '\n'.join(self.sub_stuff['rules_before']))
        self.sub_stuff['subargs'] = self.init_subargs()

    def run_once(self):
        super(iptable_base, self).run_once()
        subargs = self.sub_stuff['subargs']
        mustpass(DockerCmd(self, 'run -d', subargs, verbose=True).execute())
        self.sub_stuff['rules_during'] = self.read_iptable_rules(None)
        self.logdebug("Rules during:\n%s",
                      '\n'.join(self.sub_stuff['rules_during']))

    def postprocess(self):
        super(iptable_base, self).postprocess()
        name = self.sub_stuff['name']
        DockerContainers(self).wait_by_name(name)

        self.sub_stuff['rules_after'] = self.read_iptable_rules(None)
        self.logdebug("Rules after:\n%s",
                      '\n'.join(self.sub_stuff['rules_after']))

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
        veth = self.cntnr_veth_map().get(name)
        if veth is not None:
            self.sub_stuff['cntnr_before'] = set(self.read_iptable_rules(veth))

    def run_once(self):
        super(iptable_remove, self).run_once()
        name = self.sub_stuff['name']
        veth = self.cntnr_veth_map().get(name)
        if veth is not None:
            self.sub_stuff['cntnr_during'] = set(self.read_iptable_rules(veth))

    def postprocess(self):
        super(iptable_remove, self).postprocess()
        name = self.sub_stuff['name']
        try:
            DockerContainers(self).remove_by_name(name)
        except ValueError:
            pass  # already removed
        cntnr_before = self.sub_stuff['cntnr_before']
        cntnr_during = self.sub_stuff['cntnr_during']
        veth = self.cntnr_veth_map().get(name)
        if veth is not None:
            cntnr_after = set(self.read_iptable_rules(veth))
        self.failif(cntnr_before, "Rules found before run")
        self.failif(not cntnr_during, "No rules were added")
        self.failif(cntnr_after & cntnr_during,
                    "Rules left over after removal")
