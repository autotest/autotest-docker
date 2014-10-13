#!/usr/bin/env python

import shutil
import unittest
import tempfile
import os
import os.path

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403


class DocumentationTestBase(unittest.TestCase):

    def setUp(self):
        import documentation
        self.documentation = documentation
        self.tmpdir = tempfile.mkdtemp(self.__class__.__name__)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        self.assertFalse(os.path.isdir(self.tmpdir))


class TestDocBase(DocumentationTestBase):

    def setUp(self):
        super(TestDocBase, self).setUp()
        self.docbase = self.documentation.DocBase

    def test_init(self):
        db = self.docbase()

    def test_str(self):
        db = self.docbase()
        db.fmt = 'foobar'
        self.assertEqual(str(db), 'foobar')

    def test_repr(self):
        db = self.docbase()
        db.fmt = 'foobar'
        self.assertEqual(repr(db), 'foobar')

    def test_do_sub_good(self):
        db = self.docbase()
        db.fmt = '%(foo)s'
        db.sub_str = {'foo': 'foobar'}
        self.assertEqual(str(db), 'foobar')

    def test_do_sub_nested(self):
        db = self.docbase()
        db.fmt = '%(foo)s'
        db.sub_str = {'foo': '%(bar)s', 'bar': 'foobar'}
        self.assertEqual(str(db), '%(bar)s')

    def test_do_sub_bad_fmt(self):
        db = self.docbase()
        db.fmt = '%(foo)s'
        db.sub_str = {'bar': None}
        self.assertRaises(KeyError, str, db)

    def test_do_sub_bad_sub(self):
        db = self.docbase()
        db.fmt = ''
        db.sub_str = {'foo': 'bar'}
        self.assertEqual(str(db), '')

    def test_do_sub_bad_key(self):
        db = self.docbase()
        db.fmt = '%(bad)sfoo%(foo)s%(unknown)d'
        db.sub_str = {'foo': 'bar'}
        self.assertRaises(KeyError, str, db)

class TestSubtestDoc(DocumentationTestBase):

    subtest_docstring = 'Fake docstring'
    subtest_code = '"""\n%s\n"""\n\npass' % subtest_docstring
    subtest_base = 'somedir'
    subtest_path = '%s/subtests' % subtest_base
    subtest_basename = 'fake_subtest'
    subtest_testname = 'another/dir/%s' % subtest_basename
    subtest_fullname = '%s/%s.py' % (subtest_testname, subtest_basename)
    # These are used for testing, defined in setUp()
    subtest_fullpath = None
    base_path = None

    def setUp(self):
        super(TestSubtestDoc, self).setUp()
        self.sd = self.documentation.SubtestDoc
        self.sd.fmt = ("%(name)s "
                       "%(docstring)s "
                       "%(configuration)s ")
        # Need input file to test from w/ known contents
        self.subtest_fullpath = os.path.join(self.tmpdir,
                                             self.subtest_path,
                                             self.subtest_fullname)
        self.base_path = os.path.join(self.tmpdir, self.subtest_base)
        subtest_dir = os.path.dirname(self.subtest_fullpath)
        os.makedirs(subtest_dir)
        subtest = open(self.subtest_fullpath, 'wb')
        subtest.write(self.subtest_code)
        subtest.close()

    def test_module_filenames(self):
        filenames = self.sd.module_filenames(self.base_path)
        self.assertEqual(len(filenames), 1)
        self.assertEqual(filenames[0], self.subtest_fullpath)
        self.assertEqual(self.sd.docstring(self.subtest_fullpath),
                         self.subtest_docstring)

    def test_name(self):
        name = self.sd.name(self.subtest_fullpath)
        self.assertEqual(name, self.subtest_testname)

    def test_str(self):
        doc = self.sd(self.subtest_fullpath, {})
        test = '<p>%s %s</p>' % (self.subtest_testname, self.subtest_docstring)
        self.assertEqual(str(doc).strip(), test)
        self.assertEqual(str(doc).find('pass'), -1)

    def test_new_by_name(self):
        doc = self.sd.new_by_name(self.subtest_testname, self.base_path)
        self.assertEqual(doc.name(doc.subtest_path), self.subtest_testname)

    def test_html_summary(self):
        doc = self.sd(self.subtest_fullpath, {})
        test = '<p>%s %s</p>' % (self.subtest_testname, self.subtest_docstring)
        self.assertEqual(str(doc).strip(), test)
        # IT's big! It's Ugly! Let's just get it over with...
        test = doc.html_summary("""``docker_daemon/tls`` Subtest
====================================================================


Summary
----------

Set of test that check the container's network security.

Operational Summary
----------------------

#. Test docker tls verification.
#. Test server identity
#. Test check exclusive server identity
#. Negative test server with wrong client identity
#. Negative test client with wrong server identity

Operational Detail
----------------------

Test docker tls verification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#. Create CA certificate
#. Create certificate for daemon
#. Create certificate for client
#. Verify if docker tls verification works properly.

Test server identity
~~~~~~~~~~~~~~~~~~~~~

*  daemon -d,--selinux-enabled,--tls,--tlscert=server.crt,--tlskey=server.key
*  client %(docker_options)s,--tlsverify,--tlscacert=ca.crt

#. restart daemon with tls configuration
#. Check client connection
#. cleanup all containers and images.

Test check exclusive server identity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*  daemon --tls,--tlscert=server.crt,--tlskey=server.key
*  client --tlsverify,--tlscacert=ca.crt,--tlscert=wrongclient.crt,\
   --tlskey=wrongclient.key

#. restart daemon with tls configuration
#. Check client connection
#. cleanup all containers and images.

Negative test server with wrong client identity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*  daemon --tlsverify,--tlscacert=ca.crt,--tlscert=server.crt,\
   --tlskey=server.key
*  client --tlsverify,--tlscacert=ca.crt,--tlscert=wrongclient.crt,\
   --tlskey=wrongclient.key

#. restart daemon with tls configuration
#. Try to start docker client with wrong certs.
#. Check if client fail.
#. cleanup all containers and images.

Negative test client with wrong server identity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*  daemon --tlsverify,--tlscacert=ca.crt,--tlscert=server.crt,\
   --tlskey=server.key
*  client --tlsverify,--tlscacert=ca.crt,--tlscert=wrongclient.crt,\
   --tlskey=wrongclient.key

#. restart daemon with tls configuration
#. Try to start docker client with wrong certs.
#. Check if client fail.
#. cleanup all containers and images.

Prerequisites
------------------------------------

Openssl is installed and forward/reverse DNS is functioning for host.

Configuration
-------------------------------------

*  The option ``docker_daemon_bind`` sets special bind address.
*  The option ``docker_client_bind`` sets special client args.
*  The option ``docker_options_spec`` sets additional docker options.""")
        # def test_html_summary(self):
        # ...
        contains = ('<h1>Operational Summary</h1>',
                    '<h1>Summary</h1>',
                    '<li>Test docker tls verification.</li>')
        nocontain = ('<h1>Operational Detail</h1>',
                     '<li>Verify if docker tls verification',
                     '<h1>Configuration</h1>')
        for positive in contains:
            if test.find(positive) < 0:
                # Make failure message helpful
                self.assertEqual('"%s" not found in ->' % positive, test)
        for negative in nocontain:
            if test.find(negative) > -1:
                # Make failure message helpful
                self.assertEqual('Should not find "%s" in ->' % positive, test)


class TestSubtestDocs(DocumentationTestBase):

    subtests_docstrings = {
        'foo': '\nijjoitjsdtrnyoifdi9844\n\n\n',
        'bar': '**123456**',
        'baz': 'Section!\n~~~~~~~~~~~~~~\nSome Content'
    }

    html = ('<h1 class="title">baz Section!</h1>\n'
            '<p>Some Content</p>\n\n<p>foo ijjoitjsdtrnyoifdi9844</p>\n\n'
            '<p>bar <strong>123456</strong></p>')

    def subtest_fullpath(self, name):
        return os.path.join(self.tmpdir, 'subtests', name, name + '.py')

    def setUp(self):
        super(TestSubtestDocs, self).setUp()
        self.stds = self.documentation.SubtestDocs
        for name, content in self.subtests_docstrings.items():
            subtest_fullpath = self.subtest_fullpath(name)
            subtest_dir = os.path.dirname(subtest_fullpath)
            os.makedirs(subtest_dir)
            subtest = open(subtest_fullpath, 'wb')
            subtest.write('"""%s"""\n\npass\n' % content)
            subtest.close()

    # FIXME: When run alone, it fails, must be ext. state dep. somewhere
    def test_html(self):
        stds = str(self.stds(os.path.join(self.tmpdir)))
        haz_stuff = [stds.find('baz Section!') > -1,
                     stds.find('Some Content') > -1,
                     stds.find('foo ijjoitjsdtrnyoifdi9844') > -1,
                     stds.find('123456') > -1]
        self.assertTrue(all(haz_stuff))

    def test_exclude(self):
        stds = str(self.stds(os.path.join(self.tmpdir), exclude='baz'))
        has_baz = stds.find('Some Content')
        self.assertEqual(has_baz, -1)

if __name__ == '__main__':
    unittest.main()
