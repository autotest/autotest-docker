#!/usr/bin/env python

# Pylint runs from a different directory, it's fine to import this way
# pylint: disable=W0403

import os
import shutil
import sys
import tempfile
import types
import unittest


def mock(mod_path):
    name_list = mod_path.split('.')
    child_name = name_list.pop()
    child_mod = sys.modules.get(mod_path, types.ModuleType(child_name))
    if len(name_list) == 0:  # child_name is left-most basic module
        if child_name not in sys.modules:
            sys.modules[child_name] = child_mod
        return sys.modules[child_name]
    else:
        # New or existing child becomes parent
        recurse_path = ".".join(name_list)
        parent_mod = mock(recurse_path)
        if not hasattr(sys.modules[recurse_path], child_name):
            setattr(parent_mod, child_name, child_mod)
            # full-name also points at child module
            sys.modules[mod_path] = child_mod
        return sys.modules[mod_path]


class FakeCmdResult(object):

    def __init__(self, **dargs):
        for key, val in dargs.items():
            setattr(self, key, val)

RUN_CACHE = []


def get_run_cache():
    global RUN_CACHE
    return RUN_CACHE


def kill_run_cache():
    global RUN_CACHE
    RUN_CACHE = []


def run(command, *args, **dargs):
    command = "%s" % (command)
    get_run_cache().append({'command': command, 'args': args, 'dargs': dargs})
    return FakeCmdResult(command=command.strip(),
                         stdout="""
REPOSITORY                    TAG                 IMAGE ID                                                           CREATED             VIRTUAL SIZE
192.168.122.245:5000/fedora   32                  0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404   5 weeks ago         387 MB
fedora                        32                  0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404   5 weeks ago         387 MB
fedora                        rawhide             0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404   5 weeks ago         387 MB
192.168.122.245:5000/fedora   latest              58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9   5 weeks ago         385.5 MB
fedora                        20                  58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9   5 weeks ago         385.5 MB
fedora                        heisenbug           58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9   5 weeks ago         385.5 MB
fedora                        latest              58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9   5 weeks ago         385.5 MB
""",
                         stderr=str(dargs),
                         exit_status=len(args),
                         duration=len(dargs))

# Mock module and mock function run in one command
setattr(mock('autotest.client.utils'), 'run', run)
setattr(mock('autotest.client.utils'), 'CmdResult', FakeCmdResult)
setattr(mock('autotest.client.test'), 'test', object)
setattr(mock('autotest.client.shared.error'), 'TestFail', Exception)
setattr(mock('autotest.client.shared.error'), 'CmdError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestError', Exception)
setattr(mock('autotest.client.shared.error'), 'TestNAError', Exception)
setattr(mock('autotest.client.shared.error'), 'AutotestError', Exception)
setattr(mock('autotest.client.shared.version'), 'get_version',
        lambda: version.AUTOTESTVERSION)
mock('autotest.client.shared.base_job')
mock('autotest.client.shared.job')
mock('autotest.client.shared.utils')
mock('autotest.client.job')

import version


class ImageTestBase(unittest.TestCase):

    defaults = {}
    customs = {}
    config_section = "Foo/Bar/Baz"

    def _setup_inifile(self, cfgsection, cfgdir, cfgdict):
        osfd, filename = tempfile.mkstemp(suffix='.ini',
                                          dir=cfgdir)
        os.close(osfd)
        # ConfigSection will open again
        cfgfile = open(filename, 'wb')
        cfgfile.close()
        # ConfigDict forbids writing
        cfgsect = self.config.ConfigSection(None, cfgsection)
        for key, val in cfgdict.items():
            cfgsect.set(key, val)
        cfgsect.set('__example__', '')
        cfgsect.write(cfgfile)
        return filename

    def _setup_defaults(self):
        self.config.DEFAULTSFILE = self._setup_inifile('DEFAULTS',
                                                       self.config.CONFIGDEFAULT,
                                                       self.defaults)

    def _setup_customs(self):
        self._setup_inifile(self.config_section,
                            self.config.CONFIGCUSTOMS,
                            self.customs)

    def _make_fake_subtest(self):
        class FakeSubtestException(Exception):

            def __init__(fake_self, *args, **dargs):  # pylint: disable=E0213
                # Unittest magic pylint: disable=E1003
                super(FakeSubtestException, self).__init__()
                # Unittest magic pylint: enable=E1003

        class FakeSubtest(self.subtest.Subtest):
            version = "1.2.3"
            config_section = self.config_section
            iteration = 1
            iterations = 1

            def __init__(fake_self, *args, **dargs):  # pylint: disable=E0213
                config_parser = self.config.Config()
                fake_self.config = config_parser.get(self.config_section)
                for symbol in ('execute', 'setup', 'initialize', 'run_once',
                               'postprocess_iteration', 'postprocess',
                               'cleanup', 'failif',):
                    setattr(fake_self, symbol, FakeSubtestException)
                for symbol in ('logdebug', 'loginfo', 'logwarning', 'logerror'):
                    setattr(fake_self, symbol, lambda *_a, **_d: None)

        return FakeSubtest()

    def setUp(self):
        import config
        import images
        import subtest
        self.config = config
        self.images = images
        self.subtest = subtest
        self.config.CONFIGDEFAULT = tempfile.mkdtemp(self.__class__.__name__)
        self.config.CONFIGCUSTOMS = tempfile.mkdtemp(self.__class__.__name__)
        self._setup_defaults()
        self._setup_customs()
        self.fake_subtest = self._make_fake_subtest()

    def tearDown(self):
        shutil.rmtree(self.config.CONFIGDEFAULT, ignore_errors=True)
        shutil.rmtree(self.config.CONFIGCUSTOMS, ignore_errors=True)
        self.assertFalse(os.path.isdir(self.config.CONFIGDEFAULT))
        self.assertFalse(os.path.isdir(self.config.CONFIGCUSTOMS))
        del self.config
        del self.images
        del self.subtest


class DockerImageTestBasic(ImageTestBase):

    defaults = {'docker_path': '/foo/bar', 'docker_options': '--not_exist',
                'docker_timeout': 60.0, 'docker_repo_name': 'fedora',
                'docker_repo_tag': 'latest', 'docker_registry_host': '192.168.122.245:5000',
                'docker_registry_user': '', 'preserve_fqins': 'fedora:32, fedora:heisenbug'}
    customs = {}
    config_section = "Foo/Bar/Baz"

    def test_defaults_cli(self):
        d = self.images.DockerImages(self.fake_subtest)
        all_images = d.list_imgs()
        full_name = d.list_imgs_full_name()
        self.assertEqual(full_name,
                         ['192.168.122.245:5000/fedora:32',
                          'fedora:32',
                          'fedora:rawhide',
                          '192.168.122.245:5000/fedora:latest',
                          'fedora:20',
                          'fedora:heisenbug',
                          'fedora:latest'])

        ids = d.list_imgs_ids()
        self.assertEqual(ids,
                         ['58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9',
                          '0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404'])

        test_im = self.images.DockerImage("fedora",
                                          "latest",
                                          ("58394af373423902a1b97f209a31e3777"
                                           "932d9321ef10e64feaaa7b4df609cf9"),
                                          "5 weeks ago",
                                          "385.5 MB")
        self.assertTrue(test_im in all_images)
        self.assertEqual(all_images.index(test_im), 6)

        images = str(d.list_imgs_with_full_name(full_name[2]))
        self.assertEqual(images,
                         "[DockerImage(full_name:fedora:rawhide LONG_ID:0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404 CREATED:5 weeks ago SIZE:387 MB)]")

        images = str(d.list_imgs_with_full_name("fedora:latest"))
        exp = ("[DockerImage(full_name:192.168.122.245:5000/fedora:latest LONG_ID:58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9 CREATED:5 weeks ago SIZE:385.5 MB),"
               " DockerImage(full_name:fedora:latest LONG_ID:58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9 CREATED:5 weeks ago SIZE:385.5 MB)]")
        self.assertEqual(images, exp)

        act = self.images.DockerImages.filter_list_full_name(all_images,
                                                             "fedora:"
                                                             "latest")
        self.assertEqual(str(act), exp)

        images = str(d.list_imgs_with_full_name_components(repo_addr="192.168.122.245:5000"))
        exp = ("[DockerImage(full_name:192.168.122.245:5000/fedora:32 LONG_ID:0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404 CREATED:5 weeks ago SIZE:387 MB),"
               " DockerImage(full_name:192.168.122.245:5000/fedora:latest LONG_ID:58394af373423902a1b97f209a31e3777932d9321ef10e64feaaa7b4df609cf9 CREATED:5 weeks ago SIZE:385.5 MB)]")
        self.assertEqual(images, exp)
        act = self.images.DockerImages.filter_list_by_components(all_images,
                                                                 repo_addr='192.168.122.245:5000')
        self.assertEqual(str(act), exp)

        images = str(d.list_imgs_with_full_name_components(repo_addr="192.168.122.245:5000",
                                                           tag="32"))
        self.assertEqual(images,
                         "[DockerImage(full_name:192.168.122.245:5000/fedora:32 LONG_ID:0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404 CREATED:5 weeks ago SIZE:387 MB)]")

        images = d.list_imgs_with_image_id(all_images[2].long_id)
        self.assertEqual(str(images),
                         "[DockerImage(full_name:192.168.122.245:5000/fedora:32 LONG_ID:0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404 CREATED:5 weeks ago SIZE:387 MB),"
                         " DockerImage(full_name:fedora:32 LONG_ID:0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404 CREATED:5 weeks ago SIZE:387 MB),"
                         " DockerImage(full_name:fedora:rawhide LONG_ID:0d20aec6529d5d396b195182c0eaa82bfe014c3e82ab390203ed56a774d2c404 CREATED:5 weeks ago SIZE:387 MB)]",)

    def test_name_comparsion_dockerimage(self):
        di_ref = self.images.DockerImage("fedora_repo", "last_tag",
                                         ("0d20aec6529d5d396b195182c0eaa82bfe0"
                                          "14c3e82ab390203ed56a774d2c404"),
                                         "dd",
                                         "50 MB",
                                         "fedora_addr", "user_user")

        di_ref2 = self.images.DockerImage("fedora_repo", "last_tag",
                                          ("0d20aec6529d5d396b195182c0eaa82bfe0"
                                           "14c3e82ab390203ed56a774d2c404"),
                                          "dd",
                                          "50 MB",
                                          "fedora_addr", "user_user")

        di_dif = self.images.DockerImage("fedora3_repo", "last_tag",
                                         ("0d20aec6529d5d396b195182c0eaa82bfe0"
                                          "14c3e82ab390203ed56a774d2c404"),
                                         "dd",
                                         "50 MB",
                                         "fedora_addr", "user_user")

        full_name = "fedora_addr/user_user/fedora_repo:last_tag"
        (repo, tag, repo_addr, user) = self.images.DockerImage.split_to_component(
            full_name)
        self.assertRaises(self.images.DockerFullNameFormatError,
                          self.images.DockerImage.split_to_component, ["dd/"])
        self.assertRaises(self.images.DockerFullNameFormatError,
                          self.images.DockerImage.split_to_component,
                          ["dd/aa/ss/ss"])
        self.assertRaises(self.images.DockerFullNameFormatError,
                          self.images.DockerImage.split_to_component,
                          ["dd/aa:aa/ss"])

        self.assertRaises(self.images.DockerFullNameFormatError,
                          self.images.DockerImage.split_to_component,
                          ["<none>:<none>"])

        self.assertEqual(self.images.DockerImage.full_name_from_component(
            repo, tag, repo_addr, user), full_name)

        self.assertEqual((repo, tag, repo_addr, user),
                         ("fedora_repo", "last_tag", "fedora_addr",
                          "user_user"))
        self.assertTrue(di_ref.cmp_full_name_with_component(repo, tag, repo_addr, user))
        self.assertFalse(di_ref.cmp_full_name_with_component(repo, tag, repo_addr=repo_addr))
        self.assertTrue(di_ref.cmp_greedy(repo, repo_addr=repo_addr, user=user))
        self.assertTrue(di_ref.cmp_greedy(repo))
        self.assertTrue(di_ref.cmp_greedy(repo, repo_addr=repo_addr))
        self.assertTrue(di_ref.cmp_greedy(repo, user=user))
        self.assertTrue(di_ref.cmp_greedy(repo_addr=repo_addr))
        self.assertFalse(di_ref.cmp_greedy(repo=repo_addr))
        self.assertTrue(di_ref == di_ref2)
        self.assertFalse(di_ref == di_dif)

        self.assertTrue(self.images.DockerImage(
            "fedora_addr:44/user_user/"
            "fedora_repo:last_tag", None,
            "0d20aec6529d5d396b195182c0eaa82bfe0"
            "14c3e82ab390203ed56a774d2c404",
            "dd",
            "50 MB",
            None,
            None).cmp_full_name_with_component("fedora_repo",
                                               "last_tag",
                                               "fedora_addr:44",
                                               "user_user"))

        self.assertTrue(di_ref.cmp_id(di_ref2.short_id))
        self.assertTrue(di_ref.cmp_id(di_ref2.long_id))
        self.assertFalse(di_ref.cmp_id('11111111111'))
        self.assertFalse(di_ref.cmp_id('1111111111111111111111111111111111'))

        self.assertTrue(di_ref.cmp_full_name(di_ref2.full_name))
        self.assertFalse(di_ref.cmp_full_name(di_dif.full_name))

        config = {'docker_repo_name': 'fedora', 'docker_repo_tag': '',
                  'docker_registry_user': '', 'docker_registry_host': ''}
        act = self.images.DockerImage.full_name_from_defaults(config)
        self.assertEqual(act, 'fedora')

    def test_bastard_repo(self):
        test = "bAsTaRd-rEPo.lOcAl_hOsT:1073741824/.b+o-F_H./a.s-d_f:F.d-S_a"
        DI = self.images.DockerImage
        repo, tag, addr, user = DI.split_to_component(test)
        di = DI(repo, tag, '0' * 64, None, None, addr, user)
        self.assertEqual(di.full_name, test)

    def test_user_no_addr(self):
        test = "user/repo:tag"
        DI = self.images.DockerImage
        repo, tag, addr, user = DI.split_to_component(test)
        self.assertEqual(repo, 'repo')
        self.assertEqual(tag, 'tag')
        self.assertEqual(user, 'user')
        self.assertEqual(addr, None)

    def test_addr_no_user(self):
        test = "address:1234/repo:tag"
        DI = self.images.DockerImage
        repo, tag, addr, user = DI.split_to_component(test)
        self.assertEqual(repo, 'repo')
        self.assertEqual(tag, 'tag')
        self.assertEqual(user, None)
        self.assertEqual(addr, "address:1234")

    def test_remove_cli(self):
        d = self.images.DockerImages(self.fake_subtest, 1.0, True)
        self.assertEqual(d.remove_image_by_id('123456789012').command,
                         "/foo/bar rmi 123456789012")
        self.assertEqual(d.remove_image_by_id('123456789012').command,
                         "/foo/bar rmi 123456789012")
        self.assertEqual(d.remove_image_by_full_name('fedora:latest').command,
                         "/foo/bar rmi fedora:latest")
        image_obj = self.images.DockerImage("fedora_repo", "last_tag",
                                            ("0d20aec6529d5d396b195182c0eaa"
                                             "82bfe014c3e82ab390203ed56a774"
                                             "d2c404"),
                                            "dd",
                                            "50 MB",
                                            None, "user_user")
        self.assertEqual(d.remove_image_by_image_obj(image_obj).command,
                         "/foo/bar rmi user_user/fedora_repo:last_tag")

    def test_docker_images_lowlevel(self):
        images = self.images.DockerImages(self.fake_subtest)

        self.assertEqual(images.docker_cmd("command_pass").command,
                         '/foo/bar command_pass')

    def test_clean_all(self):
        d = self.images.DockerImages(self.fake_subtest)
        names = set(d.list_imgs_full_name())
        # staticly set in fake config, REMOVE names to be preserved
        preserve = set(['fedora:heisenbug',
                        'fedora:32',
                        '192.168.122.245:5000/fedora:latest'])
        expected = names - preserve
        kill_run_cache()
        d.clean_all(names)
        pfx = '/foo/bar rmi --force '
        cutlen = len(pfx)
        cleaned_names = set()
        for item in get_run_cache():
            command = item['command']
            self.assertTrue(command.startswith(pfx))
            cleaned_names.add(command[cutlen:])
        # no preserved names should be in either list
        self.assertEqual(cleaned_names, expected)
        self.assertTrue(cleaned_names.isdisjoint(preserve))

if __name__ == '__main__':
    unittest.main()
