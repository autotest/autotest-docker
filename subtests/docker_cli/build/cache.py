from build import BuildSubSubtest


class cache(BuildSubSubtest):

    def make_builds(self, source):
        first = source.copy()
        second = source.copy()
        # Just remote all key2's to keep tidy
        for key in first.keys():  # dict is being modified
            if key.endswith('2'):
                del first[key]
        # Move key2 values, remove key2 to keep tidy
        for key in second.keys():  # move '2' key valus
            if key.endswith('2'):
                second[key[:-1]] = second[key]  # copy value
                del second[key]  # remove 2 key
        super_make_builds = super(cache, self).make_builds
        return super_make_builds(first) + super_make_builds(second)
