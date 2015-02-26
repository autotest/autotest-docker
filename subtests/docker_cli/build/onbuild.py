from build import build_base


class onbuild(build_base):

    def make_builds(self, source):
        first = source.copy()
        second = source.copy()
        third = source.copy()
        # Just remote all key2's to keep tidy
        for key in first.keys():  # dict is being modified
            if key.endswith('2') or key.endswith('3'):
                del first[key]
        # Move key2 values, remove key2 to keep tidy
        for key in second.keys():  # move '2' key valus
            if key.endswith('2'):
                second[key[:-1]] = second[key]  # copy value
                del second[key]  # remove 2 key
            if key in ('docker_repo_name', 'docker_repo_tag',
                       'docker_registry_host', 'docker_registry_user'):
                del second[key]  # Filled in below
        # Move key3 values, remove key2 and key 3 to keep tidy
        for key in third.keys():  # move '3' key valus
            if key.endswith('3'):
                third[key[:-1]] = third[key]  # copy value
                del third[key]  # remove 3 key
            if key in ('docker_repo_name', 'docker_repo_tag',
                       'docker_registry_host', 'docker_registry_user'):
                del third[key]  # Filled in below
        super_make_builds = super(onbuild, self).make_builds
        builds = super_make_builds(first)
        second['docker_repo_name'] = builds[-1].image_name
        builds += super_make_builds(second)
        third['docker_repo_name'] = builds[-1].image_name
        builds += super_make_builds(third)
        return builds
