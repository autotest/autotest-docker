"""
Create container with tons of --name options, verify the last one sticks
"""

from create import create_base


class create_names(create_base):

    def init_name(self):
        cont = self.sub_stuff["cont"]
        name_base = cont.get_unique_name()
        first_name = name = '%s%s' % (name_base, 0)
        for number in xrange(1, self.config['names_count']):
            self.sub_stuff['subargs'] += ['--name', name]
            name = '%s%s' % (name_base, number)
        if self.config['last_name_sticks']:
            self.sub_stuff['name'] = self.sub_stuff['subargs'][-1]
        else:
            self.sub_stuff['name'] = first_name

    def postprocess(self):
        cont = self.sub_stuff["cont"]
        json = cont.json_by_name(self.sub_stuff['name'])
        # Removes container as part of test success
        super(create_names, self).postprocess()
        # Also check JSON name is expected
        self.failif(len(json) == 0)
        # docker sticks a "/" prefix on name (documented?)
        actual_name = str(json[0]['Name'][1:])
        self.failif_ne(actual_name, self.sub_stuff['name'],
                       "Actual name %s != expected name %s"
                       % (actual_name, self.sub_stuff['name']))
