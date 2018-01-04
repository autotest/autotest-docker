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


class DockerImageIncomplete(DockerImage):

    """Instances may have long_id, created, or size set to cls.UNKNOWN"""

    UNKNOWN = "unknown"

    def __init__(self, repo, tag, long_id, created, size,
                 repo_addr=None, user=None):
        dargs = {'long_id': long_id, 'created': created, 'size': size}
        for key, value in dargs.items():
            if value is None:
                value = self.__class__.UNKNOWN
                dargs[key] = value
        dargs['repo'] = repo
        dargs['tag'] = tag
        dargs['repo_addr'] = repo_addr
        dargs['user'] = user
        super(DockerImageIncomplete, self).__init__(**dargs)

    def cmp_id(self, image_id):
        if self.long_id == self.__class__.UNKNOWN:
            raise RuntimeError("Can't compare unknown image ID to %s"
                               % image_id)
        else:
            return super(DockerImageIncomplete, self).cmp_id(image_id)

    def __eq__(self, other):
        if self.long_id == self.__class__.UNKNOWN:
            # Comparing by name is only possible for non-<none>s
            if other.repo and other.tag and other.repo_addr and other.user:
                return self.cmp_greedy(other.repo, other.tag,
                                       other.repo_addr, other.user)
            return False
        return super(DockerImageIncomplete, self.__eq__(other))

    @classmethod
    def prob_is_fqin(cls, fqin_or_id):
        fqin_score = 0
        fqin_or_id = fqin_or_id.strip()
        for item in cls.split_to_component(fqin_or_id):
            if item is not None:
                fqin_score += 1
        if fqin_score > 1:
            return True
        else:
            # Only a single regex group matched
            if fqin_or_id.isalnum():
                fqin_score -= 1
            else:
                fqin_score += 1
            if len(fqin_or_id) == 12 or len(fqin_or_id) == 64:
                fqin_score -= 1
            else:
                fqin_score += 1
        return fqin_score > 0


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

    def fuzzy_img(self, fqin_or_id):
        di = self.sub_stuff['di']
        repo = None
        tag = None
        repo_addr = None
        user = None
        long_id = None
        short_id = None
        created = None
        size = None
        if DockerImageIncomplete.prob_is_fqin(fqin_or_id):
            # Greedy match (i.e. doesn't compare None values)
            imgs = di.filter_list_full_name(di.list_imgs(),
                                            fqin_or_id)
            if len(imgs) == 1:  # found it
                return imgs[0]
            # Retrieve known infos
            (repo, tag,
             repo_addr,
             user) = DockerImageIncomplete.split_to_component(fqin_or_id)
        else:
            imgs = di.list_imgs_with_image_id(fqin_or_id)
            if len(imgs) == 1:  # found it
                return imgs[0]
            if len(fqin_or_id) == 12:
                short_id = fqin_or_id
            else:
                long_id = fqin_or_id
        # Create an instance w/ whatever info. is available
        img = DockerImageIncomplete(repo, tag, long_id, created, size,
                                    repo_addr, user)
        # Possible only short ID is available
        if short_id is not None and img.short_id == img.UNKNOWN:
            img.short_id = short_id
        return img

    def initialize(self):
        super(Base, self).initialize()
        self.step_log_msgs = {}
        self.sub_stuff['dc'] = DockerContainers(self)
        self.sub_stuff['di'] = di = DockerImages(self)
        di.DICLS = DockerImageIncomplete

        default_image = self.fuzzy_img(di.default_image)
        self.sub_stuff['default_image'] = default_image

        # Can't use set of DockerImageIncomplete -> it's mutable
        preserve_images = [default_image]
        for fqin_or_id in get_as_list(self.config['preserve_fqins']):
            preserve_images.append(self.fuzzy_img(fqin_or_id))
        self.sub_stuff['preserve_images'] = preserve_images

        preserve_cnames = set(get_as_list(self.config['preserve_cnames']))
        self.sub_stuff['preserve_cnames'] = preserve_cnames
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
        preserve_images = self.sub_stuff['preserve_images']
        leftover_images = [img for img in di.list_imgs()
                           if img not in preserve_images]
        if leftover_images:
            fail_images = ("Found leftover images "
                           "from prior test: %s"
                           % (leftover_images))
            self.sub_stuff['fail_images'] = fail_images
        # Let subclasses perform the actual failing (or not)


class containers(Base):

    def run_once(self):
        super(containers, self).run_once()
        preserve_cnames = self.sub_stuff['preserve_cnames']

        dc = self.sub_stuff['dc']
        dc.remove_args = '--force=true --volumes=true'
        for name in set(dc.list_container_names()) - preserve_cnames:
            if not self.config['remove_garbage']:
                continue
            self.logwarning("Removing left behind container: %s",
                            name)
            try:
                dc.remove_by_name(name)
            except (ValueError, KeyError):
                pass  # Removal was the goal
        # Don't presume what others methods will do with this instance
        dc.remove_args = DockerContainers.remove_args

    def postprocess(self):
        # identify cleanup failures in base class
        super(containers, self).postprocess()
        if not self.config['fail_on_unremoved']:
            if self.sub_stuff['fail_containers']:
                # No test failure, but maybe a warning
                self.logwarning(self.sub_stuff['fail_containers'])
        else:
            self.failif(self.sub_stuff['fail_containers'],
                        # Value is it's own failure message
                        self.sub_stuff['fail_containers'])


class images(Base):

    def run_once(self):
        super(images, self).run_once()
        preserve_images = self.sub_stuff['preserve_images']
        di = self.sub_stuff['di']
        di.remove_args = '--force=true'
        leftover_images = [img for img in di.list_imgs()
                           if img not in preserve_images]
        for img in leftover_images:
            # another sub-subtest will take care of <none> images
            if img.repo == '' or img.repo is None:
                continue
            if not self.config['remove_garbage']:
                continue
            self.logwarning("Removing left behind: %s", img)
            try:
                di.remove_image_by_image_obj(img)
            except (ValueError, KeyError):
                pass  # Removal was the goal
        # Don't presume what others methods will do with this instance
        di.remove_args = DockerImages.remove_args

    def postprocess(self):
        # identify cleanup failures in base class
        super(images, self).postprocess()
        if not self.config['fail_on_unremoved']:
            if self.sub_stuff['fail_images']:
                self.logwarning(self.sub_stuff['fail_images'])
        else:
            self.failif(self.sub_stuff['fail_images'],
                        # Value is it's own failure message
                        self.sub_stuff['fail_images'])


class nones(Base):

    def run_once(self):
        super(nones, self).run_once()
        preserve_images = self.sub_stuff['preserve_images']
        di = self.sub_stuff['di']
        di.remove_args = '--force=true'
        leftover_images = [img for img in di.list_imgs()
                           if img not in preserve_images]
        for img in leftover_images:
            if img.repo is not None and img.repo and img.repo != '<none>':
                continue
            if not self.config['remove_garbage']:
                continue
            self.logwarning("Removing leftover <none> image: %s", img)
            try:
                di.remove_image_by_id(img.short_id)
            except (ValueError, KeyError):
                pass  # Removal was the goal
        # Don't presume what others methods will do with this instance
        di.remove_args = DockerImages.remove_args

    def postprocess(self):
        # No super-call, this method is different
        di = self.sub_stuff['di']
        preserve_images = self.sub_stuff['preserve_images']
        leftover_images = [img for img in di.list_imgs()
                           if (img not in preserve_images and
                               img.repo == '' or img.repo is None)]
        if leftover_images:
            fail_images = ("Found leftover <none>'s "
                           "from prior test: %s"
                           % (leftover_images))
            # Just in case?
            self.sub_stuff['fail_images'] = fail_images
            if not self.config['fail_on_unremoved']:
                self.logwarning(fail_images)
            else:
                self.failif(fail_images, fail_images)
