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
        dir_path = self.config['dockerfile_dir_path2']
        build_def['dockerfile_dir_path'] = self.dockerfile_dir_path(dir_path)
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
