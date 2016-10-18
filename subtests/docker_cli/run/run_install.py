from run import run_base
from dockertest.dockercmd import DockerCmd
from dockertest.output.validate import mustpass


class run_install(run_base):
    """Verify installing packages in a container is functional"""

    def init_subargs(self):
        cont = self.sub_stuff['cont']
        # Name will be used for image, must be lower-case
        self.sub_stuff['name'] = name = cont.get_unique_name().lower()
        self.sub_stuff['subargs'] += ["--name %s" % name,
                                      self.sub_stuff['fqin'],
                                      self.config['install_cmd']]

    def postprocess(self):
        super(run_install, self).postprocess()

        name = self.sub_stuff['name']
        # ancestor method must have been successful
        self.sub_stuff['containers'].append(name)

        # images with same names as containers are confusing
        eman = name[-1::-1]  # the name, backwards
        mustpass(DockerCmd(self, 'commit',
                           [name, "%s:latest" % eman]).execute())
        # mustpass() was successful
        self.sub_stuff['images'].append(name)

        eman = name[-1::-1]  # committed image
        subargs = ['-i', '--rm', eman, self.config['verify_cmd']]
        mustpass(DockerCmd(self, 'run', subargs).execute())
