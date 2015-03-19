r"""
Summary
----------

This test checks function of `docker ps --size` shows correct sizes

Operational Summary
----------------------

#.  Create couple of containers, each creates file of given size
#.  Execute docker ps -a --size
#.  Check the sizes are in given limit ($size; 1mb + $limit_per_mb * $size)
"""
from dockertest import config
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtestCaller, SubSubtest


class ps_size(SubSubtestCaller):

    """ Subtest caller """


class ps_size_base(SubSubtest):

    """ Base class """

    def _init_container(self, subargs, cmd):
        """
        Prepares dkrcmd and stores the name in self.sub_stuff['containers']
        :return: dkrcmd
        """
        name = self.sub_stuff['dc'].get_unique_name()
        subargs.append("--name %s" % name)
        self.sub_stuff['containers'].append(name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append(cmd)
        dkrcmd = DockerCmd(self, 'run', subargs, verbose=False)
        return dkrcmd

    def initialize(self):
        super(ps_size_base, self).initialize()
        # Prepare a container
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['containers'] = []

    def cleanup(self):
        """
        Cleanup the containers defined in self.sub_stuff['containers']
        """
        if self.config['remove_after_test']:
            dc = DockerContainers(self)
            dc.clean_all(self.sub_stuff.get("containers"))


class simple(ps_size_base):

    """
    Simple `docker ps -a --size` test.
    1. Create couple of containers, each creates file of given size
    2. Execute docker ps -a --size
    3. Check the sizes are in given limit ($size; 1mb + $limit_per_mb * $size)
    """

    def initialize(self):
        super(simple, self).initialize()
        self.sub_stuff['sizes'] = []

    def run_once(self):
        super(simple, self).run_once()
        dd_cmd = self.config['dd_cmd']
        for size in (int(size) for size in self.config['dd_sizes'].split()):
            if size >= 1000:
                segment = '1G'
                size = size / 1000
                self.sub_stuff['sizes'].append(size * 1000)
            else:
                segment = "1M"
                self.sub_stuff['sizes'].append(size)
            dkrcmd = self._init_container([], dd_cmd % (segment, size))
            mustpass(dkrcmd.execute())

    def postprocess(self):
        def convert_size(size):
            """ Converts the size from docker ps --size format """
            size, unit = size.split()
            return float(size) * {'B': 0.001, 'MB': 1, 'GB': 1024}[unit]

        def get_container_size(containers, name):
            """ Returns size of given container from containers list """
            for cnt in containers:
                if cnt.cmp_name(name):
                    return convert_size(cnt.size)
        super(simple, self).postprocess()
        try:
            self.sub_stuff['dc'].get_size = True
            containers = self.sub_stuff['dc'].list_containers()
            created_containers = self.sub_stuff['containers']
            sizes = self.sub_stuff['sizes']
            self.sub_stuff['dc'].get_size = False
            err = []
            for i in xrange(len(sizes)):
                size = get_container_size(containers, created_containers[i])
                exp = sizes[i]
                limit = 1 + float(self.config['limit_per_mb']) * int(exp)
                # range (size; size + limit)
                if (size > exp + limit) or (size < exp):
                    err.append("Size of %s:%s not in range %s - %s"
                               % (created_containers[i], size, exp,
                                  exp + limit))

            self.failif(err, "Following containers reported incorrect sizes:"
                        "\n%s" % "\n".join(err))
        finally:
            # Ensure get_size is disabled
            self.sub_stuff['dc'].get_size = False
