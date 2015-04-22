r"""
Summary
---------

Test output of docker Pull command

Operational Summary
----------------------

#. Try to download repository from registry
#. if docker_expected_result == PASS: fail when command exitcode != 0
    #. Check if image is in local repository.
    #. Remote image from local repository
#. If docker_expected_result == FAIL: fail when command exitcode == 0

Prerequisites
---------------------------------------------
*  A *remote* registry server
*  Image on remote registry with 'latest' and some other tag
*  Image on remote should not conflict with default test image
"""

import time
import httplib
from autotest.client.shared import error
from dockertest.subtest import SubSubtest
from dockertest.images import DockerImages
from dockertest.output import OutputGood
from dockertest.dockercmd import AsyncDockerCmd
from dockertest import subtest


class pull(subtest.SubSubtestCaller):
    pass


class pull_base(SubSubtest):

    @staticmethod
    def check_registry(registry_addr):
        conn = httplib.HTTPConnection(registry_addr)
        conn.request("GET", "/")
        r1 = conn.getresponse()
        if r1.status != 200:
            response = r1.read()
            if "docker-registry server" not in response:
                raise error.TestNAError("Registry %s is not docker registry."
                                        " Response: %s" % (registry_addr,
                                                           response))
        else:
            raise error.TestNAError("Registry %s is not"
                                    " available." % registry_addr)

    def setup(self):
        # check docker registry:
        registry_addr = self.config["docker_registry_host"]
        self.check_registry(registry_addr)

    def initialize(self):
        super(pull_base, self).initialize()
        self.sub_stuff['di'] = di = DockerImages(self)
        image_fn = di.full_name_from_defaults()
        self.sub_stuff["image_fn"] = image_fn
        # set by run_once()
        self.sub_stuff['image_list'] = []
        dkrcmd = AsyncDockerCmd(self, 'pull',
                                [image_fn])
        self.sub_stuff['dkrcmd'] = dkrcmd

    def run_once(self):
        super(pull_base, self).run_once()
        dkrcmd = self.sub_stuff['dkrcmd']
        self.loginfo("Executing background pull...")
        dkrcmd.execute()
        while not dkrcmd.done:
            self.loginfo("Pulling...")
            time.sleep(3)
            if dkrcmd.exit_status is not None:
                break
        self.sub_stuff['image_list'] = DockerImages(self).list_imgs()

    def outputcheck(self):
        # Raise exception if problems found
        OutputGood(self.sub_stuff['dkrcmd'].cmdresult)

    def exitcheck(self):
        exit_status = self.sub_stuff['dkrcmd'].exit_status
        if self.config["docker_expected_result"] == "PASS":
            self.failif(exit_status != 0,
                        "Non-zero pull exit status: %s"
                        % self.sub_stuff['dkrcmd'])
        elif self.config["docker_expected_result"] == "FAIL":
            self.failif(exit_status == 0,
                        "Zero pull exit status: Command should fail due to"
                        " wrong command arguments.")

    def existcheck(self):
        if self.config["docker_expected_result"] == "PASS":
            di = self.sub_stuff['di']
            image_fn = di.full_name_from_defaults()
            image_list = self.sub_stuff['image_list']
            img_names = [img.full_name for img in image_list]
            self.failif(image_fn not in img_names,
                        "Image %s not found in %s" % (image_fn, img_names))

    def postprocess(self):
        super(pull_base, self).postprocess()
        self.outputcheck()
        self.exitcheck()
        self.existcheck()

    def cleanup(self):
        super(pull_base, self).cleanup()
        image_list = self.sub_stuff['image_list']
        if self.config['remove_after_test'] and image_list != []:
            test_id = None
            remove = []
            # 2x loop: ID for test image, all names matching ID
            for img in image_list * 2:
                if img.full_name == self.sub_stuff['image_fn']:
                    test_id = img.long_id
                if test_id is not None and img.long_id == test_id:
                    remove.append(img.full_name)
            DockerImages(self).clean_all(remove)


class good(pull_base):
    pass
