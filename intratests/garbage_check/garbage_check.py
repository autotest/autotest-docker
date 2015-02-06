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
        ignore_fqins = set(get_as_list(self.config['ignore_fqins']))
        ignore_fqins.add(default_fqin)
        self.sub_stuff['ignore_fqins'] = ignore_fqins
        ignore_cnames = set(get_as_list(self.config['ignore_cnames']))
        self.sub_stuff['ignore_cnames'] = ignore_cnames

        existing_containers = dc.list_container_names()
        self.sub_stuff['existing_containers'] = set(existing_containers)
        existing_images = di.list_imgs_full_name()
        self.sub_stuff['existing_images'] = set(existing_images)

        self.sub_stuff['fail_containers'] = False
        self.sub_stuff['fail_images'] = False

    def postprocess(self):
        super(Base, self).postprocess()
        dc = self.sub_stuff['dc']
        ignore_cnames = self.sub_stuff['ignore_cnames']
        leftover_containers = set(dc.list_container_names()) - ignore_cnames
        if leftover_containers:
            fail_containers = ("Found leftover containers "
                               "from prior test: %s"
                               % leftover_containers)
            self.sub_stuff['fail_containers'] = fail_containers
        di = self.sub_stuff['di']
        ignore_fqins = self.sub_stuff['ignore_fqins']
        leftover_images = set(di.list_imgs_full_name()) - ignore_fqins
        if leftover_images:
            fail_images = ("Found leftover images "
                           "from prior test: %s"
                           % leftover_images)
            self.sub_stuff['fail_images'] = fail_images
        # Let subclasses perform the actual failing (or not)


class containers(Base):

    def run_once(self):
        super(containers, self).run_once()
        if not self.config['remove_garbage']:
            return  # Nothing to do
        existing_containers = self.sub_stuff['existing_containers']
        ignore_cnames = self.sub_stuff['ignore_cnames']

        dc = self.sub_stuff['dc']
        dc.remove_args = '--force=true --volumes=true'
        for name in existing_containers - ignore_cnames:
            self.logwarning("Previous test left behind container: %s",
                            name)
            try:
                dc.remove_by_name(name)
            except (ValueError, KeyError):
                pass  # Removal was the goal
        dc.remove_args = DockerContainers.remove_args

    def postprocess(self):
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
        if not self.config['remove_garbage']:
            return  # Nothing to do
        existing_images = self.sub_stuff['existing_images']
        ignore_fqins = self.sub_stuff['ignore_fqins']

        di = self.sub_stuff['di']
        di.remove_args = '--force=true'
        for name in existing_images - ignore_fqins:
            self.logwarning("Previous test left behind FQIN: %s",
                            name)
            try:
                di.remove_image_by_full_name(name)
            except (ValueError, KeyError):
                pass  # Removal was the goal
        di.remove_args = DockerImages.remove_args

    def postprocess(self):
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
        if not self.config['remove_garbage']:
            return  # Nothing to do
        di = self.sub_stuff['di']
        di.remove_args = '--force=true'
        none_imgs = [img
                     for img in di.list_imgs()
                     if img.full_name is None]
        for img in none_imgs:
            self.logwarning("Previous test left behind <none> image: %s",
                            img.short_id)
            try:
                di.remove_image_by_id(img.long_id)
            except (ValueError, KeyError):
                pass  # Removal was the goal
        di.remove_args = DockerImages.remove_args

    def postprocess(self):
        super(nones, self).postprocess()
        di = self.sub_stuff['di']
        img_names = set(di.list_imgs_full_name())
        msg = "<none> images found left over: %s" % img_names
        self.failif(self.config['fail_on_unremoved'] and
                    None in img_names, msg)
        # No test failure, but maybe a warning
        if None in img_names:
            self.logwarning(msg)
