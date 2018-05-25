r"""
Summary
----------

This test is focused on `docker images --all` specific behavior. It
checks the difference between ``docker images`` and ``docker images --all``.

Operational Summary
----------------------

#.  Create image test_a
#.  Create image test_a1 with parent test_a
#.  Create image test_b
#.  Create image test_b1 with parent test_b
#.  Untag test_a
#.  Untag test_a1 (verify intermediary images were removed too)
#.  Untag test_b1 (verify test_b was preserved)

*  Between steps 4-7 verify `docker images` and `docker history`
"""

from dockertest import config
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.output import mustpass
from dockertest.images import DockerImage, DockerImages
from dockertest.subtest import SubSubtestCaller, SubSubtest


class images_all(SubSubtestCaller):
    pass


class images_all_base(SubSubtest):

    def _init_container(self, prefix, fin, subargs, cmd):
        """
        Prepares dkrcmd and stores the name in self.sub_stuff['containers']
        :return: name
        """
        if fin is None:
            fin = DockerImage.full_name_from_defaults(self.config)
        name = self.sub_stuff['dc'].get_unique_name(prefix)
        subargs.append("--name %s" % name)
        self.sub_stuff['containers'].append(name)
        subargs.append(fin)
        subargs.append(cmd)
        mustpass(DockerCmd(self, 'run', subargs).execute())
        return name

    def _create_image(self, parent, prefix, cmd):
        """
        Creates image by executing `docker run $parent $cmd`, commiting it
        and removing the container. Also store id in self.sub_stuff['images']
        :return: [image_id, image_name]
        """
        images = self.sub_stuff['di']
        cont_name = self._init_container("test", parent, [], cmd)
        img_name = images.get_unique_name(prefix)
        dkrcmd = DockerCmd(self, "commit", [cont_name, img_name])
        img_id = mustpass(dkrcmd.execute()).stdout.strip()
##        if not img_id.startswith('sha256:'):
##            img_id = 'sha256:' + img_id         # FIXME FIXME FIXME ESM
        mustpass(DockerCmd(self, 'rm',
                           ['--force', '--volumes', cont_name]).execute())
        self.sub_stuff['images'].append(img_id)
        return [img_id, img_name]

    def initialize(self):
        super(images_all_base, self).initialize()
        # Prepare a container
        config.none_if_empty(self.config)
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['di'] = DockerImages(self)
        self.sub_stuff['containers'] = []
        self.sub_stuff['images'] = []

    def verify_images(self, test_images):
        """
        For each test_image from test_images verifies:
        1. Presence in `docker images`
        2. Presence in `docker images --all`
        3. Presence of parent in `docker history`

        test_image compounded of [$long_id, $name, $exists, $tagged, $parents]
        exists, tagged are bools set by test developer
        parents is list of parent long_ids
        """
        def format_err_str(test_images, images, imagesall):
            """ Format useful err info """
            out = "Expected images:\n"
            out += "\n".join((str(_) for _ in test_images))
            out += "\nImages:\n"
            out += "\n".join(("%s (%s)" % (_.repo, _.long_id)
                              for _ in images))
            out += "\nImages --all:\n"
            out += "\n".join(("%s (%s)" % (_.repo, _.long_id)
                              for _ in imagesall))
            return out

        def name_in(name, images):
            """ name (.repo) in list of images """
            return name in (_.repo for _ in images)

        def id_in(long_id, images):
            """ id in list of images """
#            return long_id in (_.long_id for _ in images)
            return long_id.lstrip("sha256:") in (
                _.long_id.lstrip("sha256:") for _ in images)
        images = self.sub_stuff['di'].list_imgs()
        imagesall = self.sub_stuff['dia'].list_imgs()
        import pprint;print ">>> Images:";pprint.pprint(images)
        import pprint;print ">>> ImagesAll:";pprint.pprint(imagesall)
        err_str = lambda: format_err_str(test_images, images, imagesall)
        for image in test_images:
            if image[2:4] == [False, False]:   # Non existing (nowhere)
                self.failif(id_in(image[0], imagesall), "Removed image id"
                            " '%s' in images all:\n%s" % (image[0], err_str()))
                self.failif(name_in(image[1], imagesall), "Removed image "
                            "named '%s' in images all:\n%s"
                            % (image[1], err_str()))
            elif image[3] is False:   # Untagged (id in images all)
                self.failif(name_in(image[1], imagesall), "Untagged name '%s'"
                            " in images all:\n%s" % (image[1], err_str()))
                self.failif(id_in(image[0], images), "Untagged id '%s' in "
                            "images:\n%s" % (image[0], err_str()))
                self.failif(not id_in(image[0], imagesall), "Untagged id '%s'"
                            " used in another image not present in images all"
                            ":\n%s" % (image[0], err_str()))
            else:   # Tags and ids exist everywhere
                self.failif(not id_in(image[0], images), "Image id '%s' "
                            "not found in images:\n%s" % (image[0], err_str()))
                self.failif(not id_in(image[0], imagesall), "Image id '%s'"
                            " not found in images all:\n%s"
                            % (image[0], err_str()))
                self.failif(not name_in(image[1], images), "Image named '%s' "
                            "not found in images:\n%s" % (image[1], err_str()))
                self.failif(not name_in(image[1], imagesall), "Image named "
                            "'%s' not found in images all:\n%s"
                            % (image[1], err_str()))
            if image[3] and image[4] is not None:
                history = mustpass(DockerCmd(self, 'history',
                                             ['--no-trunc', '-q',
                                              image[0]]).execute()).stdout
                for parent in image[4]:
                    self.failif(parent not in history, "Parent image '%s' of "
                                "image '%s' was not found in `docker history`:"
                                "\n%s\n%s" % (parent, image[0], history,
                                              err_str()))

    def cleanup(self):
        super(images_all_base, self).cleanup()
        if self.config['remove_after_test']:
            dc = self.sub_stuff['dc']
            dc.clean_all(self.sub_stuff.get("containers"))
            di = self.sub_stuff['di']
            di.clean_all(self.sub_stuff.get("images"))


class two_images_with_parents(images_all_base):

    """
    1. Create image test_a
    2. Create image test_a1 with parent test_a
    3. Create image test_b
    4. Create image test_b1 with parent test_b
    5. Untag test_a
    6. Untag test_a1 (verify intermediary images were removed too)
    7. Untag test_b1 (verify test_b was preserved)
    :note: Between steps 4-7 verify `docker images` and `docker history`
    """

    def initialize(self):
        super(two_images_with_parents, self).initialize()
        self.sub_stuff['sizes'] = []
        self.sub_stuff['dia'] = DockerImages(self)
        self.sub_stuff['dia'].images_args += " --all"

    def run_once(self):
        super(two_images_with_parents, self).run_once()
        # Create images
        test_a = self._create_image(None, "test_a", "touch /test_a")
        test_a1 = self._create_image(test_a[1], "test_a1", "touch /test_a1")
        test_b = self._create_image(None, "test_b", "touch /test_b")
        test_b1 = self._create_image(test_b[1], "test_b1", "touch /test_b1")
        test_a += [True, True, None]        # exists, is tagged, no parent
        test_a1 += [True, True, [test_a[0]]]  # exists, is tagged, parent
        test_b += [True, True, None]        # exists, is tagged, no parent
        test_b1 += [True, True, [test_b[0]]]  # exists, is tagged, parent
        # Verify
        self.verify_images((test_a, test_a1, test_b, test_b1))
        # Untag test_a
        mustpass(DockerCmd(self, 'rmi', [test_a[1]]).execute())
        test_a[3] = False   # exists, untagged
        # Verify
        self.verify_images((test_a, test_a1, test_b, test_b1))
        # Untag test_a.1
        mustpass(DockerCmd(self, 'rmi', [test_a1[1]]).execute())
        test_a1[2:4] = [False, False]   # doesn't exist, not tagged
        test_a[2:4] = [False, False]    # doesn't exist, not tagged
        # Verify
        self.verify_images((test_a, test_a1, test_b, test_b1))
        # Untag test_b.1
        mustpass(DockerCmd(self, 'rmi', [test_b1[1]]).execute())
        test_b1[2:4] = [False, False]  # doesn't exist, not tagged
        # Verify
        self.verify_images((test_a, test_a1, test_b, test_b1))
        # Remove the last image by id
        mustpass(DockerCmd(self, 'rmi', [test_b[0]]).execute())
        test_b[2:4] = [False, False]    # doesn't exist, not tagged
        self.verify_images((test_a, test_a1, test_b, test_b1))


class with_unused_containers(two_images_with_parents):

    """
    The same as `two_images_with_parents` only executes couple of containers
    first. (existing containers with no relation to removed images sometimes
    cause failure)
    """

    def initialize(self):
        super(with_unused_containers, self).initialize()
        for _ in xrange(10):
            self._init_container("background", None, [], "sh -c exit")
