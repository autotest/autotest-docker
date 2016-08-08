r"""
Summary
---------

Test output of docker inspect command

Operational Summary
----------------------

#. Create some docker containers
#. Run docker inspect command on them
#. Check output
"""

import json
import os
from autotest.client import utils
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.xceptions import DockerTestError


class dockerinspect(SubSubtestCaller):

    config_section = 'docker_cli/dockerinspect'


class inspect_base(SubSubtest):

    @staticmethod
    def verify_same_configs(subtest, source, comp, ignore_fields=None):
        for i in range(len(comp)):  # pylint: disable=E0012,C0200
            for key in comp[i].keys():
                if ignore_fields and key in ignore_fields:
                    continue
                subtest.failif(not (source[i][key] == comp[i][key]),
                               "CLI output differs from container config: "
                               "ID: %s, %s: %s != "
                               "%s: %s" % (comp[i]['ID'][:12],
                                           key, source[i][key],
                                           key, comp[i][key]))

    @staticmethod
    def get_cid_from_name(subtest, name):
        containers = DockerContainers(subtest).list_containers()
        return next(x.long_id for x in containers if x.container_name == name)

    def parse_cli_output(self, output):
        try:
            output_map = json.loads(output)
        except ValueError:
            self.failif(True, "Unable to parse inspect output.")
        return output_map

    @staticmethod
    def find_container_path(cid, docker_root='/var/lib/docker/'):
        """
        Finds the path to the container the same way that docker would
        :param cid: A string with the container id you want
        :param docker_root: The path to the docker root directory
        :return: The container's config path
        """
        containers = os.walk(docker_root + 'containers/').next()[1]
        search = [x for x in containers if x.startswith(cid)]
        if not search:
            raise DockerTestError("No containers found for id: %s" % (cid))
        return "%scontainers/%s/" % (docker_root, search[0])

    @staticmethod
    def build_config_map(container_path):
        """
        Builds a hash map of the config for a container given
        its directory.
        :param container_path: The path to the container or image.
        :return: A dict containing the container's entire configuration
        """
        all_files = os.walk(container_path).next()[2]
        json_files = [x for x in all_files if x.endswith('json')]
        config_data = {}
        for i in json_files:
            json_data = open(container_path + i)
            data = json.load(json_data)
            if i == 'hostconfig.json':
                data = {u'HostConfig': data}
            config_data = dict(config_data.items() + data.items())
            json_data.close()
        return config_data

    def get_config_maps(self, cids,
                        docker_root='/var/lib/docker/'):
        """
        Builds a list of config maps similar to the 'docker inspect'
        command.
        :param cids: A list of the partial or fullhash IDs
                     of the containers or images you want configs for.
        :param docker_root: The path to the docker root directory.
        :return: A list of config maps.
        """
        paths = [self.find_container_path(x, docker_root) for x in cids]
        configs = [self.build_config_map(x) for x in paths]
        return configs

    @staticmethod
    def create_simple_container(subtest):
        fin = DockerImage.full_name_from_defaults(subtest.config)
        name = utils.generate_random_string(12)
        subargs = ["--name=%s" % (name),
                   fin,
                   "/bin/bash",
                   "-c",
                   "'/bin/true'"]
        nfdc = DockerCmd(subtest, 'run', subargs)
        mustpass(nfdc.execute())
        if not subtest.sub_stuff or not subtest.sub_stuff['containers']:
            subtest.sub_stuff['containers'] = [name]
        else:
            subtest.sub_stuff['containers'] += [name]
        return name

    def cleanup(self):
        super(inspect_base, self).cleanup()
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            dc.clean_all(self.sub_stuff.get('containers', []))


class inspect_container_simple(inspect_base):

    def initialize(self):
        super(inspect_container_simple, self).initialize()
        self.sub_stuff['name'] = self.create_simple_container(self)

    def run_once(self):
        super(inspect_container_simple, self).run_once()
        subargs = [self.sub_stuff['name']]
        nfdc = DockerCmd(self, "inspect", subargs)
        self.sub_stuff['cmdresult'] = mustpass(nfdc.execute())
        # Log details when command is successful
        self.logdebug(nfdc.cmdresult)

    def postprocess(self):
        super(inspect_container_simple, self).postprocess()
        cli_output = self.parse_cli_output(self.sub_stuff['cmdresult'].stdout)
        check_fields = self.config['check_fields'].split(',')
        for field in check_fields:
            self.failif(field not in cli_output[0],
                        "Field: '%s' not found in output." % (field))
