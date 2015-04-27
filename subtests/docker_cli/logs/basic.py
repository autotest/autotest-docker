"""
#. Create a container, run a docker logs command
#. Capture new logs output
#. Start the container, capture new logs output
#. Verify container state
#. Verify produced output with expected output
"""

from time import sleep
from logs import Base
from datetime import datetime


class basic(Base):

    def initialize(self):
        super(basic, self).initialize()
        dc = self.sub_stuff['dc']
        name = dc.get_unique_name()
        self.sub_stuff['cntnr_names'].append(name)
        # Items unique to this subtest
        self.sub_stuff['cntnr'] = None
        self.sub_stuff['logs_cmd'] = {'before_start': None,
                                      'after_start': None}
        self.sub_stuff['expected_stdout'] = {'before_start': '',
                                             'after_start': None}

    def run_once(self):
        super(basic, self).run_once()
        cntnr = self.create_cntnr('date', '"+foobar: %H"')
        name = self.scrape_name(cntnr.subargs)

        logs_cmd = self.sub_stuff['logs_cmd']
        logs_cmd['before_start'] = self.logs_cmd(name)

        cntnr = self.start_cntnr(name)  # blocking on exit
        now = datetime.now()
        # Most likely failure at hour-increment
        if now.second > 58:  # allow 2 second window for docker start
            sleep(3)
            now = datetime.now()
        #  minute-level accuracy: only hour is important
        magic = 'foobar:'
        if now.hour < 10:
            hour_s = '%s 0%s' % (magic, str(now.hour))
        else:
            hour_s = '%s %s' % (magic, str(now.hour))
        self.sub_stuff['expected_stdout']['after_start'] = hour_s
        logs_cmd['after_start'] = self.logs_cmd(name)

    def postprocess(self):
        super(basic, self).postprocess()
        logs_cmd = self.sub_stuff['logs_cmd']
        expected_stdout = self.sub_stuff['expected_stdout']
        for key in ('before_start', 'after_start'):
            stdout = logs_cmd[key].stdout.strip()
            expected = expected_stdout[key].strip()
            self.failif(stdout != expected,
                        'Logs command output "%s" != Expected "%s"'
                        % (stdout, expected))
