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
        import docdeps
        import documentation
        self.docdeps = docdeps
        self.documentation = documentation
        self.tmpdir = tempfile.mkdtemp(self.__class__.__name__)
        # Don't let changes in module affect unittesting
        documentation.set_default_base_path(self.tmpdir)
        docdeps.DocItem.empty_value = '<None>'
        documentation.ConfigINIParser.undoc_option_doc = (
            'Undocumented Option, please fix!')
        documentation.SummaryVisitor.exclude_names = (
            'operational detail', 'prerequisites', 'configuration')
        documentation.DefaultDoc.item_fmt = '%(option)s%(desc)s%(value)s'
        documentation.ConfigDoc.item_fmt = '%(option)s%(desc)s%(value)s'
        documentation.ConfigDoc.def_item_fmt = ('%(option)s%(desc)s%(value)s'
                                                '%(def_value)s')
        documentation.SubtestDoc.fmt = ("%(name)s "
                                        "%(docstring)s "
                                        "%(configuration)s ")
        documentation.SubtestDoc.NoINIString = ('Note: Subtest does not '
                                                'have any default '
                                                'configuration')
        documentation.SubtestDoc.ConfigDocClass = documentation.ConfigDoc

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        self.assertFalse(os.path.isdir(self.tmpdir))


class TestDocItem(DocumentationTestBase):

    def setUp(self):
        super(TestDocItem, self).setUp()
        self.DocItem = self.docdeps.DocItem

    def test_init(self):
        style_one = self.DocItem(1, 2, 3, 4)
        style_two = self.DocItem(subthing=1, option=2, desc=3, value=4)
        unordered = self.DocItem(desc=3, subthing=1, value=4, option=2)
        mixed = self.DocItem(1, desc=3, value=4, option=2)
        self.assertEqual(style_one, style_two)
        self.assertEqual(style_two, unordered)
        self.assertEqual(unordered, mixed)

    def test_wrong_args(self):
        self.assertRaises(TypeError, self.DocItem)
        self.assertRaises(TypeError, self.DocItem, 1, 2, 3)
        self.assertRaises(TypeError, self.DocItem, 1, 2, 3, 4, 5)
        self.assertRaises(TypeError, self.DocItem, subthing=1, desc=3)
        self.assertRaises(TypeError, self.DocItem, subthing=1, desc=3)

    def test_fields_asdict(self):
        keys = ('subthing', 'option', 'desc', 'value')
        values = (None, None, None, None)
        dargs = dict(zip(keys, values))
        foobar = self.DocItem(**dargs)
        self.assertEqual(foobar.fields, keys)
        self.assertEqual(foobar.asdict(), dargs)
        self.assertEqual(foobar, self.DocItem(**foobar.asdict()))

    def test_read_only(self):
        foobar = self.DocItem(desc=3, subthing=1, value=4, option=2)
        self.assertRaises(AttributeError, foobar.__setattr__, 'option', None)
        self.assertRaises(AttributeError, foobar.__delattr__, 'value')
        self.assertRaises(AttributeError, delattr, foobar, 'fields')


class TestConfigINIParser(DocumentationTestBase):

    def setUp(self):
        super(TestConfigINIParser, self).setUp()
        self.DocItem = self.docdeps.DocItem
        self.CIP = self.documentation.ConfigINIParser

    def test_empty(self):
        foo = self.CIP.from_string('')
        bar = self.CIP.from_string(' ')
        baz = self.CIP.from_string('\n')
        bob = self.CIP.from_string('\n\n\n\n')
        joe = self.CIP.from_string('\n\t  \n')
        for test in (foo, bar, baz, bob, joe):
            self.assertEqual(test, ())
            self.assertRaises(IOError, getattr, test, 'subthing_names')
            self.assertRaises(IOError, getattr, test, 'subtest_name')
            self.assertRaises(IOError, getattr, test, 'subsub_names')

    def test_empty_sec(self):
        foo = self.CIP.from_string('[foo]')
        bar = self.CIP.from_string('[foo]\n          \n')
        baz = self.CIP.from_string('\n[foo] #bar\n#baz')
        bob = self.CIP.from_string('[foo]\n#: = bar')
        joe = self.CIP.from_string('#:foo\n[bar]\n            \t\t\t\t\n[baz]')
        for test in (foo, bar, baz, bob, joe):
            self.assertEqual(test, ())
        for test in (foo, bar, baz, bob):
            self.assertEqual(test.subthing_names, ('foo',))
            self.assertEqual(test.subtest_name, 'foo')
            self.assertEqual(test.subsub_names, tuple())
        # Could throw exception, for now just make sure it works
        self.assertTrue('baz' in joe.subthing_names)
        self.assertTrue('bar' in joe.subthing_names)
        # These mos def should throw exceptions
        self.assertRaises(IOError, getattr, joe, 'subtest_name')
        self.assertRaises(IOError, getattr, joe, 'subsub_names')

    def test_one_undoc(self):
        expt = self.DocItem(subthing='foo',
                            option='option',
                            desc=self.CIP.undoc_option_doc,
                            value='value')
        test = self.CIP.from_string('[foo]\noption=value')
        self.assertEqual(len(test), 1)
        self.assertEqual(test, (expt,))

    def test_two_undoc(self):
        expt1 = self.DocItem(subthing='foo',
                             option='option1',
                             desc=self.CIP.undoc_option_doc,
                             value='value1')
        expt2 = self.DocItem(subthing='foo',
                             option='option2',
                             desc=self.CIP.undoc_option_doc,
                             value='value2')
        test = self.CIP.from_string('[foo]\noption1=value1\n\noption2: value2\t\t\n')
        self.assertEqual(len(test), 2)
        self.assertTrue(expt1 in test)
        self.assertTrue(expt2 in test)

    def test_dupe(self):
        expt = self.DocItem(subthing='foo',
                            option='option',
                            desc='description',
                            value='value')
        test = self.CIP.from_string('[foo]\noption=value\n#: description\n'
                                    'option :value\t\t\n')
        self.assertEqual(len(test), 1)
        self.assertTrue(expt in test)

    def test_value_cont(self):
        expt = self.DocItem(subthing='foo',
                            option='option',
                            desc=self.CIP.undoc_option_doc,
                            value='value more value')
        test = self.CIP.from_string('[foo]\n'
                                    'option =   value    \n'
                                    '   more\t\t\n'
                                    '                    \t\tvalue\t\t')
        self.assertEqual(len(test), 1)
        self.assertTrue(expt in test)

    def test_correct_names(self):
        expt1 = self.DocItem(subthing='foo',
                             option='option1',
                             desc=self.CIP.undoc_option_doc,
                             value='value1')
        expt2 = self.DocItem(subthing='foo',
                             option='option2',
                             desc='description second line',
                             value='value2')
        expt3 = self.DocItem(subthing='foo/bar',
                             option='option3',
                             desc=self.CIP.undoc_option_doc,
                             value='value')
        test = self.CIP.from_string('[foo]\n'
                                    'option1=value1\n'
                                    '#:       description    \n'
                                    '#: second line\n\n\n\n'
                                    'option2 : value2\t\t\n'
                                    '[foo/bar]\n'
                                    'option3 =\n'
                                    '                value\n\n')
        self.assertEqual(len(test), 3)
        self.assertEqual(test.subtest_name, 'foo')
        self.assertEqual(test.subsub_names, ('foo/bar',))
        expt_test = tuple([expt1, expt2, expt3])
        # This also verifies stripping of line continuation, empty first value
        self.assertEqual(test, expt_test)

    def test_newline_sub(self):
        test = self.CIP.from_string('[foo]\n'
                                    '#: line1{n}line2\n'
                                    'option = value')
        self.assertEqual(len(test), 1)
        di = test[0]
        lines = di.desc.splitlines()
        self.assertEqual(len(lines), 2)

    def test_tab_sub(self):
        test = self.CIP.from_string('[foo]\n'
                                    '#: line1{n}\n'
                                    '#:     {t}line2{n}\n'
                                    '#:     {t}line3{n}\n'
                                    '#:{n}\n'
                                    '#:\n'
                                    'option = value')
        self.assertEqual(len(test), 1)
        di = test[0]
        lines = di.desc.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[1], '     line2')
        self.assertEqual(lines[2], '     line3')


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

    def test_do_sub_method(self):
        # This will be a different "self"
        def bar(_self_, key):
            _self_.called_bar = True
            return unicode('bar')
        try:
            setattr(self.docbase, 'bar', bar)
            setattr(self.docbase, 'called_foo', False)
            setattr(self.docbase, 'called_bar', False)
            db = self.docbase()

            def foo(key):
                db.called_foo = True
                return 0xf00
            db.fmt = '%(bar)X%(foo)s'
            db.sub_method = {'foo': db.bar,
                             'bar': foo}
            expected = 'F00bar'
            self.assertEqual(str(db), expected)
            self.assertTrue(db.called_foo)
            self.assertTrue(db.called_bar)
        finally:  # Just for safety's sake, put it back to stock
            delattr(self.docbase, 'bar')
            delattr(self.docbase, 'called_foo')
            delattr(self.docbase, 'called_bar')

    def test_sub_method_args(self):
        db = self.docbase()
        db.called_foo = False
        db.called_bar = False

        def foo(it_works=True):
            db.called_foo = it_works
            return ('foo', 'bar')

        def bar(x, y, z):
            db.called_bar = True
            return ('bar', x + y + z)
        db.fmt = '%(bar)x%(foo)s'
        db.sub_method_args = {foo: None,
                              lambda a, b, c: bar(a, b, c): (507, 3210, 123)}
        expected = 'f00bar'
        self.assertEqual(str(db), expected)
        self.assertTrue(db.called_foo)
        self.assertTrue(db.called_bar)

    def test_multi_sub(self):
        def baz(_self_, ch):
            return ('baz', ch)
        try:
            setattr(self.docbase, 'baz', baz)
            db = self.docbase()
            db.fmt = '%(foo)s%(BAR)sba%(baz)c'
            db.sub_str = {'foo': 'foo'}

            def bar(key):
                return key.lower()
            db.sub_method = {'BAR': bar}
            db.sub_method_args = {db.baz: 'z'}
            expected = 'foobarbaz'
            self.assertEqual(str(db), expected)
        finally:
            delattr(self.docbase, 'baz')


# TODO: Test ConfigDoc class (don't forget to set default_base_path)
class TestConfigDoc(DocumentationTestBase):

    # Note: Some of the strings below are wrapped on purpose!
    defaults_ini = """[DEFAULTS]
# Don't change this file, or any file under this tree!
#
# Instead, copy the files you want to modify under config_custom/
# (anywhere), and modify those copyies.  They will override
# all settings and sections defined here (config_defaults/)

#: API Version number applying to all bundled tests
config_version = 0.7.7

#: Autotest version dependency for framework (or override for individual tests)
autotest_version =
   0.16.0-master-66-g9aaee



#: Subtests and SubSubtests names to skip (CSV)
disable =

##### docker command options

#: Docker default options (before subcommand)
docker_path = /usr/bin/docker

#: Global docker command options to use
docker_options = -D

#: Max runtime in seconds for any docker command (auto-converts to float)
docker_timeout = 300.0

##### docker content options

#: Default registry settings for testing
#: (blank if not applicable)
docker_repo_name =
#: Default image settings for testing
#: (blank if not applicable)
docker_repo_tag =

#: remote components (host:port)
docker_registry_host =
#: remote components (username)
docker_registry_user =




##### Operational testing options

#: Attempt to remove all created containers/images during test
remove_after_test = yes

#: Deprecated Legacy cleanup options, DO NOT USE FOR NEW TESTS
try_remove_after_test =
   %(remove_after_test)s

##### Environment checking options

#: CSV of checker pathnames to skip, relative to 'envchecks' subdirectory
envcheck_skip =

#: CSV of possibly existing image names to ignore
envcheck_ignore_fqin =
#: CSV of possibly existing image IDs to ignore
envcheck_ignore_iids =
"""

    defaults_rst = """
docker_repo_nameDefault registry settings for testing (blank if not applicable)<None>
autotest_versionAutotest version dependency for framework (or override for individual tests)0.16.0-master-66-g9aaee
envcheck_ignore_fqinCSV of possibly existing image names to ignore<None>
envcheck_ignore_iidsCSV of possibly existing image IDs to ignore<None>
docker_registry_hostremote components (host:port)<None>
docker_pathDocker default options (before subcommand)/usr/bin/docker
disableSubtests and SubSubtests names to skip (CSV)<None>
remove_after_testAttempt to remove all created containers/images during testyes
docker_registry_userremote components (username)<None>
docker_optionsGlobal docker command options to use-D
envcheck_skipCSV of checker pathnames to skip, relative to 'envchecks' subdirectory<None>
config_versionAPI Version number applying to all bundled tests0.7.7
docker_timeoutMax runtime in seconds for any docker command (auto-converts to float)300.0
docker_repo_tagDefault image settings for testing (blank if not applicable)<None>
try_remove_after_testDeprecated Legacy cleanup options, DO NOT USE FOR NEW TESTS%(remove_after_test)s
"""

    def setUp(self):
        super(TestConfigDoc, self).setUp()
        self.ConfigDoc = self.documentation.ConfigDoc
        self.DefaultDoc = self.documentation.DefaultDoc
        # So changes in module don't affect unittesting
        os.makedirs(os.path.join(self.tmpdir,
                                 'config_defaults/subtests/docker_cli'))
        self.defaults_path = os.path.join(self.tmpdir, 'config_defaults',
                                          'defaults.ini')
        defaults = open(self.defaults_path, 'wb')
        defaults.write(self.defaults_ini)
        self.documentation.set_default_base_path(self.tmpdir)

    def test_defaults_render(self):
        defaultdoc = self.DefaultDoc(self.defaults_path)
        self.assertEqual(str(defaultdoc).strip(), self.defaults_rst.strip())

    def test_ini_filenames(self):
        # defaults should not be expressed from ConfigDoc, only DefaultDoc
        self.assertEqual(self.ConfigDoc.ini_filenames(),
                         tuple())

    # FIXME: Need more tests


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
        # Need input file to test from w/ known contents
        self.subtest_fullpath = os.path.join(self.tmpdir,
                                             self.subtest_path,
                                             self.subtest_fullname)
        self.base_path = os.path.join(self.tmpdir, self.subtest_base)
        # Don't allow class to search elsewhere!
        self.documentation.set_default_base_path(self.base_path)
        # Don't test configuration parsing here
        self.sd.NoINIString = ''
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

    def test_rst(self):
        class MySD(self.sd):
            conv = self.sd.rst_summary
        doc = MySD(self.subtest_fullpath)
        test = '%s %s' % (self.subtest_testname, self.subtest_docstring)
        self.assertEqual(str(doc).strip(), test)
        self.assertEqual(str(doc).find('pass'), -1)

    def test_new_by_name(self):
        doc = self.sd.new_by_name(self.subtest_testname, self.base_path)
        self.assertEqual(doc.name(doc.subtest_path), self.subtest_testname)

    def test_html_summary(self):
        class MySD(self.sd):
            conv = self.sd.html_summary
        doc = MySD(self.subtest_fullpath)
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

Openssl is installed and forward/reverse DNS is functioning for host.""")
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
        self.stds.default_base_path = self.tmpdir
        self.stds.stdc.default_base_path = self.tmpdir
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
