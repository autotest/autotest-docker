r"""
Summary
---------

Tests the ``docker save`` and ``docker load`` commands.

Operational Summary
----------------------

#.  prepare image
#.  save image
#.  remove image
#.  load image
#.  check results
#.  (some subsubtests) check content of the image

Prerequisites
---------------

Configuration
---------------
"""

import os
import random
import threading

from autotest.client import utils
from autotest.client.shared import error
from dockertest import subtest, xceptions
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd, NoFailDockerCmd
from dockertest.images import DockerImage, DockerImages
from dockertest.output import OutputGood
from dockertest.subtest import SubSubtest


class WorkerThread(threading.Thread):

    """ Executes objects from queue and stores the output in self.results """

    def __init__(self, queue, i):
        super(WorkerThread, self).__init__(name="test-worker-%s" % i)
        self.daemon = True
        self.finished = False
        self.interrupt = False
        self.queue = queue
        self.results = []

    def run(self):
        for name, job in self.queue:
            if self.interrupt:
                raise RuntimeError("Thread interrupted")
            self.results.append((name, job.execute()))
        self.finished = True    # Make sure there were no exceptions...

    def __str__(self):
        return ("%s\nfinished = %s\ninterrupt = %s\nqueue=%s\nresults=%s"
                % (self.getName(), self.finished, self.interrupt, self.queue,
                   self.results))


class save_load(subtest.SubSubtestCaller):

    """ Subtest caller """


class save_load_base(SubSubtest):

    """ Initialize couple of variables and removes all containters/images """

    def _init_container(self, name, cmd):
        """
        :return: tuple(container_cmd, container_name)
        """
        if self.config.get('run_options_csv'):
            subargs = [arg for arg in
                       self.config['run_options_csv'].split(',')]
        else:
            subargs = []
        if name is True:
            name = self.sub_stuff['cont'].get_unique_name("test", length=4)
        elif name:
            name = name
        if name:
            subargs.append("--name %s" % name)
        fin = DockerImage.full_name_from_defaults(self.config)
        subargs.append(fin)
        subargs.append(cmd)
        container = DockerCmd(self, 'run', subargs, verbose=False)
        return container, name

    def initialize(self):
        super(save_load_base, self).initialize()
        self.sub_stuff["containers"] = []
        self.sub_stuff["images"] = []
        self.sub_stuff["cont"] = DockerContainers(self)
        self.sub_stuff["img"] = DockerImages(self)

    def cleanup(self):
        super(save_load_base, self).cleanup()
        # Auto-converts "yes/no" to a boolean
        containers = self.sub_stuff['cont']
        if self.config['remove_after_test']:
            for cont in self.sub_stuff["containers"]:
                conts = containers.list_containers_with_name(cont)
                if conts == []:
                    return  # container doesn't exist, clean
                elif len(conts) > 1:
                    msg = ("Multiple containers matches name %s, not "
                           "removing any of them...", cont)
                    raise xceptions.DockerTestError(msg)
                NoFailDockerCmd(self, 'rm', ['--force', '--volumes', cont],
                                verbose=False).execute()
            for image in self.sub_stuff["images"]:
                try:
                    dkrimg = self.sub_stuff['img']
                    self.logdebug("Removing image %s", image)
                    dkrimg.remove_image_by_full_name(image)
                    self.logdebug("Successfully removed test image: %s",
                                  image)
                except error.CmdError, exc:
                    error_text = "tagged in multiple repositories"
                    if error_text not in exc.result_obj.stderr:
                        raise


class simple(save_load_base):

    """ Basic test, executes container, saves it and loads it again. """

    def initialize(self):
        super(simple, self).initialize()
        rand_name = utils.generate_random_string(8).lower()
        self.sub_stuff["rand_name"] = rand_name

        self.sub_stuff['containers'].append(rand_name)
        self.sub_stuff["images"].append(rand_name)

        dkrcmd = self._init_container(rand_name,
                                      self.config['docker_data_prep_cmd'])[0]

        cmdresult = dkrcmd.execute()
        if cmdresult.exit_status != 0:
            error.TestNAError("Unable to prepare env for test: %s" %
                              (cmdresult))

        rand_name = self.sub_stuff["rand_name"]
        cid = self.sub_stuff["cont"].list_containers_with_name(rand_name)

        self.failif(cid == [],
                    "Unable to search container with name %s: details :%s" %
                    (rand_name, cmdresult))

        dkrcmd = DockerCmd(self, 'commit', [rand_name, rand_name])

        cmdresult = dkrcmd.execute()
        if cmdresult.exit_status != 0:
            error.TestNAError("Unable to prepare env for test: %s" %
                              (cmdresult))
        dkrcmd = DockerCmd(self, 'rm', [rand_name])
        cmdresult = dkrcmd.execute()
        if cmdresult.exit_status != 0:
            error.TestNAError("Failed to cleanup env for test: %s" %
                              (cmdresult))

    def run_once(self):
        super(simple, self).run_once()  # Prints out basic info
        self.loginfo("Starting docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        # Save image
        save_cmd = self.config['save_cmd']
        self.sub_stuff['save_ar'] = (save_cmd %
                                     {"image": self.sub_stuff["rand_name"],
                                      "tmpdir": self.tmpdir})

        dkrcmd = DockerCmd(self, 'save',
                           [self.sub_stuff['save_ar']],
                           verbose=True)
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmdresult_save'] = dkrcmd.execute()

        if self.sub_stuff['cmdresult_save'].exit_status != 0:
            # Pass error to postprocess
            return

        # Delete image
        dkrcmd = DockerCmd(self, 'rmi',
                           [self.sub_stuff["rand_name"]],
                           verbose=True)
        # Runs in background
        self.sub_stuff['cmdresult_del'] = dkrcmd.execute()

        # Load image
        load_cmd = self.config['load_cmd']
        self.sub_stuff['load_ar'] = (load_cmd %
                                     {"image": self.sub_stuff["rand_name"],
                                      "tmpdir": self.tmpdir})

        dkrcmd = DockerCmd(self, 'load',
                           [self.sub_stuff['load_ar']],
                           verbose=True)
        dkrcmd.verbose = True
        # Runs in background
        self.sub_stuff['cmdresult_load'] = dkrcmd.execute()

    def postprocess(self):
        super(simple, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected

        OutputGood(self.sub_stuff['cmdresult_save'])
        OutputGood(self.sub_stuff['cmdresult_load'])

        str_save = self.sub_stuff['cmdresult_save']
        str_load = self.sub_stuff['cmdresult_load']
        str_del = self.sub_stuff['cmdresult_del']

        self.failif(str_save.exit_status != 0,
                    "Problem with save cmd detail :%s" %
                    str_save)

        self.failif(str_load.exit_status != 0,
                    "Problem with load cmd detail :%s" %
                    str_load)

        self.failif(str_del.exit_status != 0,
                    "Problem with del cmd detail :%s" %
                    str_del)

        img_name = self.sub_stuff["rand_name"]
        images = self.sub_stuff["img"].list_imgs_with_full_name(img_name)
        self.failif(images == [], "Unable to find loaded image.")


class stressed_load(save_load_base):

    """ Multiple loads at the same time test """

    def initialize(self):
        """
        1) Generate list of random $names and $repeat_count number of `docker
           load` commands associated to them
        2) Run container for each name which saves the $name to a file
        3) Commit the container to $name image
        4) Remove the container
        """
        super(stressed_load, self).initialize()
        # Generate $count random unique nonexisting image names
        self.sub_stuff['load_cmds'] = []        # tuple(name, dkrcmd)
        self.sub_stuff['cmdresults_save'] = []  # results of dkr save
        self.sub_stuff['cmdresults_del'] = []   # resutls of dkr rmi
        self.sub_stuff['cmdresults_load'] = []  # tuple(name, dkr load result)

        rand_names = []
        while len(rand_names) < self.config['image_count']:
            name = utils.generate_random_string(8).lower()
            if (name not in rand_names
                    and not os.path.exists(os.path.join(self.tmpdir, name))):
                rand_names.append(name)
                subargs = [self.config['load_cmd'] % {"image": name,
                                                      "tmpdir": self.tmpdir}]
                for _ in xrange(self.config['repeat_count']):
                    load_cmd = DockerCmd(self, 'load', subargs)
                    self.sub_stuff['load_cmds'].append((name, load_cmd))

        random.shuffle(self.sub_stuff['load_cmds'])     # randomize the order
        self.sub_stuff['rand_names'] = rand_names

        for rand_name in rand_names:
            self.sub_stuff['containers'].append(rand_name)
            self.sub_stuff["images"].append(rand_name)

            cmd = "sh -c 'echo TEST: %s > /test_file'" % rand_name
            dkrcmd, name = self._init_container(rand_name, cmd)
            self.sub_stuff['containers'].append(name)

            cmdresult = dkrcmd.execute()
            if cmdresult.exit_status != 0:
                error.TestNAError("Unable to prepare env for test: %s" %
                                  (cmdresult))

            cid = self.sub_stuff["cont"].list_containers_with_name(rand_name)

            self.failif(cid == [],
                        "Unable to search container with name %s: details :%s"
                        % (rand_name, cmdresult))

            dkrcmd = DockerCmd(self, 'commit', [rand_name, rand_name])

            cmdresult = dkrcmd.execute()
            if cmdresult.exit_status != 0:
                error.TestNAError("Unable to prepare env for test: %s" %
                                  (cmdresult))
            dkrcmd = DockerCmd(self, 'rm', [rand_name])
            cmdresult = dkrcmd.execute()
            if cmdresult.exit_status != 0:
                error.TestNAError("Failed to cleanup env for test: %s" %
                                  (cmdresult))

    def run_once(self):
        """
        1) Save&remove all generated images
        2) Spawn $thread_count workers, which simultaneously execute generated
           `docker load` commands. The order is randomized.
        3) Check if threads finished properly
        """
        super(stressed_load, self).run_once()  # Prints out basic info
        self.loginfo("Starting docker command, timeout %s seconds",
                     self.config['docker_timeout'])

        # First create and save all images
        for rand_name in self.sub_stuff['rand_names']:
            # Save image
            save_cmd = self.config['save_cmd']
            subargs = [save_cmd % {"image": rand_name, "tmpdir": self.tmpdir}]
            dkrcmd = DockerCmd(self, 'save', subargs, verbose=False)
            self.sub_stuff['cmdresults_save'].append(dkrcmd.execute())
            if self.sub_stuff['cmdresults_save'][-1].exit_status != 0:
                # Pass error to postprocess
                return
            # Delete image
            dkrcmd = DockerCmd(self, 'rmi', [rand_name], verbose=False)
            self.sub_stuff['cmdresults_del'].append(dkrcmd.execute())

        threads = []
        count = self.config['thread_count']
        # one piece of the cmds; +1 to always go through all of them
        piece = (len(self.sub_stuff['load_cmds']) / count) + 1
        for i in xrange(count):
            cmds = self.sub_stuff['load_cmds'][i * piece:(i + 1) * piece]
            threads.append(WorkerThread(cmds, i))

        try:
            for thread in threads:
                thread.start()

            for i in xrange(len(threads)):
                threads[i].join()
                self.failif(threads[i].finished is not True, "Worker thread%s"
                            " did not finished properly, check the log.\n%s"
                            % (i, "\n".join((str(_) for _ in threads))))
                self.sub_stuff['cmdresults_load'].extend(threads[i].results)
        finally:        # Make sure they are always interrupted...
            for thread in threads:
                thread.interrupt = True

    def postprocess(self):
        """
        1) Check all the save/del commands status
        2) Accumulate results per-name
        3) Check load results
            # a. successful execution (disabled due BZ1132479)
            b. verify that at least one command executed properly
            c. check if all images exists in `docker images`
            d. run container per each image and verify content of the test_file
        """
        def check_result(result):
            OutputGood(result)
            self.failif(result.exit_status != 0, "Non-zero exit status of %s"
                        % (result))

        super(stressed_load, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected
        for result in self.sub_stuff['cmdresults_save']:
            check_result(result)
        for result in self.sub_stuff['cmdresults_del']:
            check_result(result)
        # Split results per-name
        results = {}
        for name, result in self.sub_stuff['cmdresults_load']:
            if name in results:
                results[name].append(result)
            else:
                results[name] = [result]

        str_results = "Load results:"
        for name, res in results.iteritems():
            str_results += "\nResults of '" + name + "'\n  "
            str_results += "\n  ".join([str(_).replace('\n', '\n    ')
                                        for _ in res])
        for name, res in results.iteritems():
            one_pass = False
            for result in res:
                # FIXME: Reconsider this check when BZ1132479 is resolved
                # self.failif(result.exit_status == 0 and one_pass, "Load of "
                #             "existing tag %s exited with 0\n%s"
                #             % (name, str_results))
                if result.exit_status == 0:
                    one_pass = True
            self.failif(one_pass is not True, "None of tags %s were loaded "
                        "successfully\n%s" % (name, str_results))

            # Check image presence
            images = self.sub_stuff["img"].list_imgs_with_full_name(name)
            self.failif(images == [], "Unable to find loaded image.\n%s"
                        % str_results)

            # Execute the loaded image and check the file...
            cntr = self.sub_stuff['cont'].get_unique_name("test", length=4)
            dkrcmd = DockerCmd(self, "run", ['--rm', "--name %s" % cntr,
                                             name, "cat /test_file"])
            self.sub_stuff['containers'].append(cntr)
            result = dkrcmd.execute()
            self.failif("TEST: %s" % name not in result.stdout, "/test_file "
                        "content is not 'TEST: $NAME', image was probably "
                        "corrupted...\nCheck results:\n%s\n%s"
                        % (result, str_results))
