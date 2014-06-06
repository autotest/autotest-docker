"""
Test docker events captured during simple container run

1. Listen for events
2. Run /bin/true container
3. Check parsing of events and container events present
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import re
from string import Template
import time
import datetime
from dockertest.subtest import Subtest
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import NoFailDockerCmd
from dockertest.dockercmd import AsyncDockerCmd
from dockertest.xceptions import DockerValueError

# TODO: Turn this into a general module?
cid_regex = re.compile(r'\s+([a-z0-9]{64})\:\s+')
dt_regex = re.compile(r'\[(\d{4}-\d{2}-\d{2})\s+' # date part
                      r'(\d{2}:\d{2}:\d{2})\s+' # time part
                      r'([+-]?\d{4})\s+'  # UTC offset part
                      r'([a-zA-Z]+)\]\s+') # Timezone part
ymd_regex = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
hms_regex = re.compile(r'(\d{2})\:(\d{2})\:(\d{2})')
source_regex = re.compile(r'\s+\(from\s+%s\)\s+'
                          % DockerImage.repo_split_p.pattern)
operation_regex = re.compile(r'\s+(\w+)$')  # final word chars

def event_dt(line):
    try:
        dt_mo = dt_regex.search(line)
        # utc offset
        utc_offset_hours = int(dt_mo.group(3)) / 100.0  # remove +/-
        utc_offset = datetime.timedelta(hours=utc_offset_hours)
        ymd_mo = ymd_regex.search(dt_mo.group(1))
        year, month, day = ymd_mo.groups()
        hms_mo = hms_regex.search(dt_mo.group(2))
        hour, minute, second = hms_mo.groups()
        dt = datetime.datetime(int(year), int(month), int(day),
                               int(hour), int(minute), int(second))
        dt += utc_offset
        return dt
    except (AttributeError, TypeError, ValueError):  # regex.search() failed
        return None

def event_cid(line):
    mobj = cid_regex.search(line)
    if mobj is not None:
        return mobj.group(1)
    else:
        return None

def event_source(line):
    mobj = source_regex.search(line)
    if mobj is not None:
        # Verifies formatting
        fqin = "".join([s for s in mobj.group(1, 3, 4, 5)
                        if s is not None])
        return fqin
    else:
        return None

def event_operation(line):
    mobj = operation_regex.search(line)
    if mobj is not None:
        return mobj.group(1)
    else:
        return None

def event_details(line):
    # TODO: An event class object?
    return {'datetime':event_dt(line),
            'source':event_source(line),
            'operation':event_operation(line)}

def is_dupe_event(needle, haystack):
    for event in haystack:
        # Fastest comparison order
        if (needle['datetime'] == event['datetime'] and
            needle['source'] == event['source'] and
            needle['operation'] == event['operation']):
            return True
    return False

def parse_event(line):

    """
    Return tuple(CID, {DETAILS}) from parsing line

    :param line: String-like containing a single event line
    :returns: tuple(CID, {DETAILS}) from parsing line or None if unparseable
    """
    cid = event_cid(line)
    details = event_details(line)
    if cid is None or details['datetime'] is None:
        return None  # unparseable line
    else:
        return (cid, details)

def parse_events(lines, slop=None):

    """
    Return list of tuples for valid lines returned by parse_events()

    :param lines: String containing events, one per line
    :param slop: number of unparseable lines to tollerate, None/- to disable
    :returns: List of tuple(CID, {DETAILS}) as returned from parse_events()
    """
    sloppy = []
    result = []
    n_lines = 0
    for line in lines.splitlines():
        n_lines += 1
        if len(line) < 64:   # len of a cid
            sloppy.append(line)
            continue
        cid_details = parse_event(line)
        if cid_details is not None:
            result.append(cid_details)
        else:
            sloppy.append(line)
        if slop is not None and slop >= 0:
            n_slop = len(sloppy)
            if n_slop > slop:
                raise DockerValueError("Excess slop (>%d) encountered after "
                                       "parsing (%d) events (success on %d). "
                                       " Garbage: %s"
                                       % (slop, n_lines, n_lines - n_slop,
                                          sloppy))
    return result

def events_by_cid(events_list, previous=None):
    """
    Return a dictionary, mapping of cid to de-duplicated event-details list

    :param events_list: List of tuple(CID, {DETAILS}) from parse_events()
    :param previous: Possibly overlapping prior result from events_by_cid()
    :returns: dict-like mapping cid to de-duplicated event-details list
    """
    if previous is None:
        dct = {}
    else:
        dct = previous  # in-place update
    for cid, details in events_list:
        previous_events = dct.get(cid)
        if previous_events is None:
            previous_events = dct[cid] = []  # in-place update (below)
        if not is_dupe_event(details, previous_events):
            # don't assume it belongs at end
            previous_events.append(details)
            # using key is faster then custom compare function
            previous_events.sort(key=lambda details: details['datetime'])
    return dct  # possibly same as previous


class events(Subtest):
    config_section = 'docker_cli/events'

    def initialize(self):
        super(events, self).initialize()
        dc = self.stuff['dc'] = DockerContainers(self)
        fullname = dc.get_unique_name(prefix=self.config['name_prefix'])
        fqin = DockerImage.full_name_from_defaults(self.config)
        # generic args have spots for some value substitution
        mapping = {'NAME':fullname, 'IMAGE':fqin}
        subargs = []
        for arg in self.config['run_args'].strip().split(','):
            tmpl = Template(arg)
            # Ignores placeholders not in mapping
            subargs.append(tmpl.safe_substitute(mapping))
        # test container executed later
        self.stuff['nfdc'] = NoFailDockerCmd(self, 'run', subargs)
        self.stuff['nfdc_cid'] = None
        # docker events command executed later
        events_cmd = AsyncDockerCmd(self, 'events', ['--since=0'])
        self.stuff['events_cmd'] = events_cmd
        self.stuff['events_cmdresult'] = None
        # These will be removed as expected events for cid are identified
        leftovers = self.config['expect_events'].strip().split(',')
        self.stuff['leftovers'] = leftovers
        for key, value in self.stuff.items():
            self.logdebug("init %s = %s", key, value)

    def run_once(self):
        super(events, self).run_once()
        dc = self.stuff['dc']
        # Start listening
        self.stuff['events_cmd'].execute()
        # Do something to make new events
        cmdresult = self.stuff['nfdc'].execute()
        cid = self.stuff['nfdc_cid'] = cmdresult.stdout.strip()
        while True:
            _json = dc.json_by_long_id(cid)
            if len(_json) > 0 and _json[0]["State"]["Running"]:
                self.loginfo("Waiting for test container to exit...")
                time.sleep(3)
            else:
                break
        if self.config['rm_after_run']:
            self.loginfo("Removing test container...")
            try:
                dc.kill_container_by_long_id(cid)
            except ValueError:
                pass  # container isn't running, this is fine.
            dcmd = NoFailDockerCmd(self, 'rm', ['--force', '--volumes', cid])
            dcmd.execute()
        # No way to know how long async events take to pass through :S
        self.loginfo("Sleeping %s seconds for events to catch up",
                     self.config['wait_stop'])
        time.sleep(self.config['wait_stop'])
        # Kill off docker events after 1 second
        events_cmd = self.stuff['events_cmd']
        self.stuff['events_cmdresult'] = events_cmd.wait(timeout=1)

    def postprocess(self):
        super(events, self).postprocess()
        stdout = self.stuff['events_cmdresult'].stdout.strip()
        # one-line (about) minimum
        self.failif(len(stdout) < 80, "Output too short: '%s'" % stdout)
        all_events = parse_events(stdout)
        cid_events = events_by_cid(all_events)
        cid = self.stuff['nfdc_cid']
        self.failif(cid not in cid_events,
                    'Test container cid %s does not appear in events' % cid)
        test_events = cid_events[cid]
        for event in test_events:
            if event['operation'] in self.stuff['leftovers']:
                self.stuff['leftovers'].remove(event['operation'])
            else:
                self.logwarning("Untested event: %s", event)
        self.failif(len(self.stuff['leftovers']) > 0,
                    "Expected event operation(s) %s for cid %s not found"
                    % (self.stuff['leftovers'], self.stuff['nfdc_cid']))
        self.loginfo("All expected events were located")
        # Fail test if too much unparseable garbage
        all_events = parse_events(stdout,
                                  self.config['unparseable_allowance'])

    def cleanup(self):
        super(events, self).cleanup()
        if self.config['try_remove_after_test']:
            cid = self.stuff['nfdc_cid']
            dc = self.stuff['dc']
            try:
                dc.kill_container_by_long_id(cid)
            except ValueError:
                pass  # container isn't running, this is fine.
            dcmd = DockerCmd(self, 'rm', ['--force', '--volumes', cid])
            dcmd.execute()  # don't care if this fails
