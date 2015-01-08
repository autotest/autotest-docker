from run import run_base


class run_names(run_base):
    # Verify behavior when multiple --name options passed

    def init_subargs(self):
        cont = self.sub_stuff["cont"]
        name_base = cont.get_unique_name()
        names = []
        for number in xrange(self.config['names_count']):
            name = ('%s_%d' % (name_base, number))
            names.append(name)
            self.sub_stuff['containers'].append(name)  # just in case
        self.sub_stuff['subargs'] += ["--name %s" % name for name in names]
        if self.config['last_name_sticks']:
            self.sub_stuff['expected_name'] = names[-1]
        else:
            self.sub_stuff['expected_name'] = names[0]
        super(run_names, self).init_subargs()

    def run_once(self):
        super(run_names, self).run_once()
        cid = self.sub_stuff['cid'] = self.sub_stuff['dkrcmd'].stdout.strip()
        self.sub_stuff['containers'].append(cid)
        try:
            self.sub_stuff["cont"].wait_by_long_id(cid)
        except ValueError:
            pass  # container already finished and exited

    def postprocess(self):
        super(run_names, self).postprocess()
        cont = self.sub_stuff["cont"]
        json = cont.json_by_long_id(self.sub_stuff['cid'])
        self.failif(len(json) == 0)
        # docker sticks a "/" prefix on name (documented?)
        actual_name = str(json[0]['Name'][1:])
        self.failif(actual_name != self.sub_stuff['expected_name'],
                    "Actual name %s != expected name %s"
                    % (actual_name, self.sub_stuff['expected_name']))
