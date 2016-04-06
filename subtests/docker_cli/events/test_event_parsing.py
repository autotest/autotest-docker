# -*- python -*-
#
from unittest2 import TestCase, main        # pylint: disable=unused-import
import autotest  # pylint: disable=unused-import
from dockertest.output import DockerTime
import events


class TestEventParsing(TestCase):
    def test_1_09(self):
        """
        docker-1.9 format: container events
        """
        t = ["2016-04-06T09:53:33.265109190-04:00",
             "2016-04-06T09:53:38.048694595-04:00",
             "2016-04-06T09:53:41.016729639-04:00"]
        cid = ("39b75e2aef85774dc545acc9998f0c44"
               "d0af5f1baf32617e8bc5ed5f998cc558")
        source = "registry.access.redhat.com/rhel7/rhel:latest"

        event_log = ("{t[0]} {cid}: (from {source}) create\n"
                     "{t[1]} {cid}: (from {source}) start\n"
                     "{t[2]} {cid}: (from {source}) die\n".format(**locals()))
        keys = ['datetime', 'identifier', 'operation', 'source']
        expect = [
            (cid, dict(zip(keys, [DockerTime(t[0]), cid, 'create', source]))),
            (cid, dict(zip(keys, [DockerTime(t[1]), cid, 'start',  source]))),
            (cid, dict(zip(keys, [DockerTime(t[2]), cid, 'die',    source])))]

        actual = events.parse_events(event_log)
        self.maxDiff = None
        self.assertEqual(actual, expect)

    def test_1_09_fqin(self):
        """
        docker-1.9 format: image events
        """
        t = ['2016-04-05T15:46:35.284845995-04:00',
             '2016-04-05T15:46:35.344527102-04:00',
             '2016-04-05T15:46:35.467081301-04:00']
        fqins = ['docker.io/stackbrew/centos:7',
                 'double_tag_c5dv:',
                 'double_tag_c5dv:latest_fikfjiub']
        actions = ['pull', 'tag', 'tag']
        event_log = ("{t[0]} {fqins[0]}: {actions[0]}\n"
                     "{t[1]} {fqins[1]}: {actions[1]}\n"
                     "{t[2]} {fqins[2]}: {actions[2]}\n".format(**locals()))
        expect = []
        for i in range(3):
            expect.append((fqins[i], {'datetime':   DockerTime(t[i]),
                                      'identifier': fqins[i],
                                      'operation':  actions[i],
                                      'source':     None}))
        actual = events.parse_events(event_log)
        self.assertEqual(actual, expect)

    def test_1_10(self):
        """
        docker-1.10 format: container and network events
        """
        t = ["2016-04-06T09:54:06.640353011-04:00",
             "2016-04-06T09:54:07.096096286-04:00",
             "2016-04-06T09:54:07.108386649-04:00",
             "2016-04-06T09:54:07.442663135-04:00",
             "2016-04-06T09:54:07.846336619-04:00",
             "2016-04-06T09:55:00.000000000-04:00"]
        cid = ("ae5f8ee3cdc14512fbc6f908f06cc859"
               "0b53d0eb9e36cf543165d130f1169a0e")

        nid = ("aa5e8221edf314708c2e0fbc80b671b2"
               "e11464c87c5bd52b93a01c38538d978b")

        source = "registry.access.redhat.com/rhel7/rhel:latest"

        # Long list of Key=Value pairs emitted in parentheses. IRL these
        # are output in random order each time, so a better test would
        # place "image=etc" (the only part we care about) at the beginning,
        # middle, and end of the string. pylint: disable=W0612
        extras = ("Release=56, Vendor=Red Hat, Inc., Name=rhel7/rhel,"
                  " Authoritative_Registry=registry.access.redhat.com,"
                  " BZComponent=rhel-server-docker,"
                  " Build_Host=somewhere.redhat.com, Version=7.2,"
                  " image=registry.access.redhat.com/rhel7/rhel:latest,"
                  " name=events_c36O, Architecture=x86_64")

        # The actual docker events output, with commonalities factored out
        event_log = """
{t[0]} container create {cid} ({extras})
{t[1]} network connect {nid} (container={cid}, name=bridge, type=bridge)
{t[2]} container start {cid} ({extras})
{t[3]} container die {cid} ({extras})
{t[4]} network disconnect {nid} (name=bridge, type=bridge, container={cid})
{t[5]} container archive-path {cid} (ignore this)
""".format(**locals())
        keys = ['identifier', 'object', 'operation', 'source']
        expect = [
            (cid, dict(zip(keys, [cid, 'container', 'create',       source]))),
            (nid, dict(zip(keys, [nid, 'network',   'connect',      None]))),
            (cid, dict(zip(keys, [cid, 'container', 'start',        source]))),
            (cid, dict(zip(keys, [cid, 'container', 'die',          source]))),
            (nid, dict(zip(keys, [nid, 'network',   'disconnect',   None]))),
            (cid, dict(zip(keys, [cid, 'container', 'archive-path', None])))]
        for i, e in enumerate(expect):
            e[1]['datetime'] = DockerTime(t[i])

        actual = events.parse_events(event_log)
        self.maxDiff = None
        self.assertEqual(actual, expect)

    def test_1_10_fqin(self):
        """
        docker-1.10 format: image events
        """
        t = ['2016-04-06T18:55:12.788172829-04:00',
             '2016-04-06T18:55:12.912976416-04:00',
             '2016-04-06T18:55:13.138072788-04:00',
             '2016-04-06T18:55:13.212209086-04:00']
        fqin = 'docker.io/stackbrew/centos:7'
        cid = ('sha256:'
               '61b442687d681ef80a7b1ae148ed5ce7'
               '5a94d5fcca94315378839b3ad240f314')
        actions = ['pull', 'tag', 'tag', 'tag']
        # (used only in format string) pylint: disable=W0612
        extras = ("build-date=2015-12-23, license=GPLv2,"
                  " name=docker.io/stackbrew/centos, vendor=CentOS")

        # FIXME: we should probably extract the name= field...
        event_log = """
{t[0]} image {actions[0]} {fqin} ({extras}, name=docker.io/stackbrew/centos)
{t[1]} image {actions[1]} {cid} ({extras}, name=d_t_force_qvqe)
{t[2]} image {actions[2]} {cid} ({extras}, name=d_t_force_qvqe:latest_lhftqp)
{t[3]} image {actions[3]} {cid} ({extras}, name=d_t_force_qvqe:latest_lhftqp)
""".format(**locals())

        # Basically: first log is fqin pull, the rest are tag with CID
        expect = [(fqin, {})]
        for i in range(3):
            expect.append((cid, {}))
        for i in range(4):
            expect[i][1]['datetime']   = DockerTime(t[i])
            expect[i][1]['identifier'] = expect[i][0]
            expect[i][1]['operation']  = actions[i]
            expect[i][1]['object']     = 'image'
            expect[i][1]['source']     = None

        actual = events.parse_events(event_log)
        self.maxDiff = None
        self.assertEqual(actual, expect)
