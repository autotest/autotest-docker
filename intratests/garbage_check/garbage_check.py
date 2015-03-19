r"""
Summary
---------

Check, and optionally remove extra non-default containers and
images from the local registry.

Operational Summary
----------------------

#. Check for unexpected running containers
#. Kill unexpected running containers
#. Remove unexpected containers
#. Remove unexpected images

Prerequisites
---------------

Customized configuration listing expected containers and images.
"""

from dockertest.subtest import SubSubtestCaller
from dockertest.subtest import SubSubtest
from dockertest.containers import DockerContainers
from dockertest.images import DockerImage
from dockertest.images import DockerImages
from dockertest.config import get_as_list


class garbage_check(SubSubtestCaller):
    # This runs between EVERY subtest, okay, to be more quiet.
    step_log_msgs = {}

    def initialize(self):
        super(garbage_check, self).initialize()
        # Some runtime messages are added
        self.step_log_msgs = {}


class Base(SubSubtest):

    # This runs between EVERY subtest, okay, to be more quiet.
    step_log_msgs = {}

    def initialize(self):
        super(Base, self).initialize()
        self.step_log_msgs = {}
        self.sub_stuff['dc'] = dc = DockerContainers(self)
        self.sub_stuff['di'] = di = DockerImages(self)
        default_fqin = DockerImage.full_name_from_defaults(self.config)
        self.sub_stuff['default_fqin'] = default_fqin
        preserve_fqins = set(get_as_list(self.config['preserve_fqins']))
        preserve_fqins.add(default_fqin)
        self.sub_stuff['preserve_fqins'] = preserve_fqins
        preserve_cnames = set(get_as_list(self.config['preserve_cnames']))
        self.sub_stuff['preserve_cnames'] = preserve_cnames

        existing_containers = dc.list_container_names()
        self.sub_stuff['existing_containers'] = set(existing_containers)
        existing_images = di.list_imgs_full_name()
        self.sub_stuff['existing_images'] = set(existing_images)

        self.sub_stuff['fail_containers'] = False
        self.sub_stuff['fail_images'] = False

    def postprocess(self):
        super(Base, self).postprocess()
        dc = self.sub_stuff['dc']
        preserve_cnames = self.sub_stuff['preserve_cnames']
        leftover_containers = set(dc.list_container_names()) - preserve_cnames
        if leftover_containers:
            fail_containers = ("Found leftover containers "
                               "from prior test: %s"
                               % leftover_containers)
            self.sub_stuff['fail_containers'] = fail_containers
        di = self.sub_stuff['di']
        preserve_fqins = self.sub_stuff['preserve_fqins']
        leftover_images = set(di.list_imgs_full_name()) - preserve_fqins
        if '' in leftover_images:
            leftover_images.remove('')
        none_imgs = [img.short_id
                     for img in di.list_imgs()
                     if img.full_name is '']
        # TODO: cfg. option for preserving image by ID.
        none_imgs = set(none_imgs)
        if leftover_images or none_imgs:
            fail_images = ("Found leftover images "
                           "from prior test: %s"
                           % (leftover_images | none_imgs))
            self.sub_stuff['fail_images'] = fail_images
        # Let subclasses perform the actual failing (or not)


class containers(Base):

    def run_once(self):
        super(containers, self).run_once()
        existing_containers = self.sub_stuff['existing_containers']
        preserve_cnames = self.sub_stuff['preserve_cnames']

        dc = self.sub_stuff['dc']
        dc.remove_args = '--force=true --volumes=true'
        for name in existing_containers - preserve_cnames:
            if not self.config['remove_garbage']:
                continue
            self.logwarning("Removing left behind container: %s",
                            name)
            try:
                dc.remove_by_name(name)
            except (ValueError, KeyError):
                pass  # Removal was the goal
        dc.remove_args = DockerContainers.remove_args

    def postprocess(self):
        # identify cleanup failures in base class
        super(containers, self).postprocess()
        self.failif(self.config['fail_on_unremoved'] and
                    self.sub_stuff['fail_containers'],
                    # Value is it's own failure message
                    self.sub_stuff['fail_containers'])
        # No test failure, but maybe a warning
        if self.sub_stuff['fail_containers']:
            self.logwarning(self.sub_stuff['fail_containers'])


class images(Base):

    def run_once(self):
        super(images, self).run_once()
        existing_images = self.sub_stuff['existing_images']
        preserve_fqins = self.sub_stuff['preserve_fqins']

        di = self.sub_stuff['di']
        # Can't use di.clean_all() because result is needed
        di.remove_args = '--force=true'
        for name in existing_images - preserve_fqins:
            # another sub-subtest will take care of <none> images
            if name == '':
                continue
            if not self.config['remove_garbage']:
                continue
            self.logwarning("Removing left behind: %s",
                            name)
            try:
                di.remove_image_by_full_name(name)
            except (ValueError, KeyError):
                pass  # Removal was the goal
        di.remove_args = DockerImages.remove_args

    def postprocess(self):
        # identify cleanup failures in base class
        super(images, self).postprocess()
        self.failif(self.config['fail_on_unremoved'] and
                    self.sub_stuff['fail_images'],
                    # Value is it's own failure message
                    self.sub_stuff['fail_images'])
        # No test failure, but maybe a warning
        if self.sub_stuff['fail_images']:
            self.logwarning(self.sub_stuff['fail_images'])


class nones(Base):

    def run_once(self):
        super(nones, self).run_once()
        di = self.sub_stuff['di']
        # Can't use di.clean_all() because result is needed
        di.remove_args = '--force=true'
        none_imgs = [img
                     for img in di.list_imgs()
                     if img.full_name is '']
        # TODO: cfg. option for preserving image by ID.
        for img in none_imgs:
            if not self.config['remove_garbage']:
                continue
            self.logwarning("Removing left behind <none> image: %s",
                            img.short_id)
            try:
                di.remove_image_by_id(img.long_id)
            except (ValueError, KeyError):
                pass  # Removal was the goal
        di.remove_args = DockerImages.remove_args

    def postprocess(self):
        # identify cleanup failures in base class
        super(nones, self).postprocess()
        di = self.sub_stuff['di']
        img_names = set(di.list_imgs_full_name())
        msg = "<none> images found left over: %s" % img_names
        self.failif(self.config['fail_on_unremoved'] and
                    '' in img_names, msg)
        # No test failure, but maybe a warning
        if None in img_names:
            self.logwarning(msg)
