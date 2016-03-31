"""
Test key names in json config files as shown by inspect subcommand
https://bugzilla.redhat.com/show_bug.cgi?id=1092773

1. Create some docker containers
2. Run docker inspect command on them and an image
3. Check output keys againt known keys and a regex
"""

from dockerinspect import inspect_base
from dockertest.output import mustpass
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.xceptions import DockerTestError
import re


class inspect_keys(inspect_base):

    def initialize(self):
        super(inspect_keys, self).initialize()
        # make a container to check
        self.create_simple_container(self)
        image = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['image'] = image

    def inspect_and_parse(self, subargs):
        nfdc = DockerCmd(self, "inspect", subargs)
        cmdresult = mustpass(nfdc.execute())
        # Log details when command is successful
        self.logdebug(nfdc.cmdresult)
        return self.parse_cli_output(cmdresult.stdout)

    def run_once(self):
        super(inspect_keys, self).run_once()
        # inspect a container
        subargs = self.sub_stuff['containers']
        json = self.inspect_and_parse(subargs)
        # in-place modify, expression used for clarity
        self.sub_stuff['container_config'] = self.filter_keys(json)

        # inspect an image
        subargs = [self.sub_stuff['image']]
        json = self.inspect_and_parse(subargs)
        # in-place modify, expression used for clarity
        self.sub_stuff['image_config'] = self.filter_keys(json)

    def filter_keys(self, json):
        json0 = json[0]
        # Keys in Labels should not be checked for style
        try:
            json0['Config']['Labels'] = {}
            self.logdebug("Cleared Config.Labels branch")
        except KeyError:
            self.logdebug("Config.Labels branch not found?")
        # These are data-keys, not structural, ignore names
        try:
            # New in docker 1.9.1
            networks = json0['NetworkSettings']['Networks']
            for network in networks.keys():
                # Child key names still need checking
                dummy_key = 'RenamedForTesting_%s' % network
                original_value = networks[network]
                del networks[network]
                networks[dummy_key] = original_value
                self.logdebug("NetworkSettings.Networks.%s -> "
                              "NetworkSettings.Networks.%s",
                              network, dummy_key)
        except KeyError:
            self.logdebug("NetworkSettings.Networks.* branches not found?")
        self.logdebug("JSON object after filtering:\n%s\n", json)
        return json

    def get_keys(self, coll):
        """Return a list of all dictionary keys, included nested in lists"""
        if isinstance(coll, list):
            return sum([self.get_keys(_) for _ in coll], [])
        if isinstance(coll, dict):
            return sum([self.get_keys(_) for _ in coll.values()], coll.keys())
        return []

    def assert_regex(self, keys, name):
        restr = self.config['key_regex']
        if not (restr.startswith('^') and restr.endswith('$')):
            raise DockerTestError("key_regex: %s will not match whole "
                                  "strings. It must start with ^ and "
                                  "end with $" % (restr))
        regex = re.compile(restr)
        fails = [x for x in keys if not bool(regex.match(x))]
        self.failif(fails,
                    "Keys: %s, do not match "
                    "regex: %s in %s" % (fails, regex.pattern, name))

    def assert_keys(self, check_keys, keys, name):
        fails = [x for x in check_keys if x not in keys]
        self.failif(fails,
                    "Keys: %s not found in config"
                    " for %s." % (fails, name))

    def postprocess(self):
        super(inspect_keys, self).postprocess()
        # verify image keys
        name = "image: %s" % (self.sub_stuff['image'])
        keys = self.get_keys(self.sub_stuff['image_config'])
        # Makes copy-paste into json_reformat / json_verify easier
        xmsg = "failing json:\n%s\n" % self.config['image_config']
        try:
            if self.config['image_keys']:
                check_keys = self.config['image_keys'].split(',')
                self.assert_keys(check_keys, keys, name)
            if self.config['key_regex']:
                self.assert_regex(keys, name)

            # verify container keys
            name = "container: %s" % (self.sub_stuff['containers'][0])
            keys = self.get_keys(self.sub_stuff['container_config'])
            xmsg = "failing json:\n%s\n" % self.config['container_config']
            if self.config['container_keys']:
                check_keys = self.config['container_keys'].split(',')
                self.assert_keys(check_keys, keys, name)
            if self.config['key_regex']:
                self.assert_regex(keys, name)
        except:
            self.logdebug(xmsg)
            raise
