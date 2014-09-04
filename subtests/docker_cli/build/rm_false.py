"""
This tests the `docker build --rm` feature + with the docker caching on
1. Create container using $part dockerfile (--rm=True)
2. Create container using $full dockerfile (--rm=False)
3. Check the number of created containers and images (part & full contain
the same basics, so not all containers should be created, cache is in use)
"""
from build import build_base


class rm_false(build_base):

    def initialize(self):
        super(rm_false, self).initialize()
        build_def = {}
        self.sub_stuff['builds'].append(build_def)
        build_def['image_name'] = ("%s_2" %
                                   self.sub_stuff['builds'][0]['image_name'])
        path = self.config['dockerfile_path2']
        build_def['dockerfile_path'] = self.dockerfile_path(path)
        build_def['intermediary_containers'] = True

    def run_once(self):
        super(rm_false, self).run_once()
        containers_pre = self.sub_stuff['existing_containers']
        containers_post = self.sub_stuff['dc'].list_container_ids()
        self.failif(len(containers_pre) != len(containers_post),
                    "Number of containers before and after first build "
                    "(--rm=True) is not the same.\nBefore: %s\nAfter: %s"
                    % (containers_pre, containers_post))
        self._build_container(self.sub_stuff['builds'][1],
                              [self.config['docker_build_options2']])

    def postprocess(self):
        super(rm_false, self).postprocess()
        containers_pre = self.sub_stuff['existing_containers']
        containers_post = self.sub_stuff['dc'].list_container_ids()
        # No new containers
        self.failif(len(containers_pre) == len(containers_post), "No new "
                    "containers created in build (rm=False).")
        # Too many new containers
        _all = self.config['dockerfile_all_containers']
        _new = self.config['dockerfile_new_containers']
        if _all != _new:
            self.failif(len(containers_pre) + _all == len(containers_post),
                        "Number of containers before and after second build "
                        "(--rm=False) is exactly of %s higher, cache was "
                        "probably not used and containers for all (even "
                        "cached) steps were created." % _all)
        # Other count
        self.failif(len(containers_pre) + _new != len(containers_post),
                    "Number of containers before and after second build "
                    "(--rm=False) is not of %s containers higher. That's "
                    "really weird...).\nBefore: %s\nAfter: %s"
                    % (_new, containers_pre, containers_post))
