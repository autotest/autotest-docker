r"""
Summary
----------

Test read & write to various host-paths as container volumes

Operational Summary
----------------------

1. Setup volumes for testing, use known locations / data.
2. Start container(2), attempt access / read files
3. Verify tested output/results match expected values.

Operational Detail
------------------

*  volumes_rw: Attempt to read, then write a file from a host path
   volume inside a container.  Intended to test NFS, SMB, and other
   'remote' filesystem mounts.
*  volumes_one_source: Have multiple containers mount a directory
   and then write to files in that directory simultaneously.


Prerequisites
-------------------

*  Remote filesystems are mounted and accessible on host system.
*  Containers have access to read & write files w/in mountpoints
"""

import os
import os.path
import hashlib
from autotest.client import utils
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.output import OutputGood
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.xceptions import DockerTestNAError
from dockertest.xceptions import DockerTestError
from dockertest import environment
from dockertest.config import get_as_list


class run_volumes(SubSubtestCaller):

    def initialize(self):
        super(run_volumes, self).initialize()
        ptc = self.config['pretest_cmd'].strip()
        if isinstance(ptc, basestring) and ptc != '':
            utils.run(ptc, timeout=self.config['docker_timeout'])


class volumes_base(SubSubtest):

    @staticmethod
    def make_test_files(host_path):
        # Symlink can't be mountpoint (e.g. for NFS, SMB, etc.)
        read_fn = utils.generate_random_string(24)
        write_fn = utils.generate_random_string(24)
        read_data = utils.generate_random_string(24)
        read_hash = hashlib.md5(read_data).hexdigest()
        tr_file = open(os.path.join(host_path, read_fn), 'wb')
        tr_file.write(read_data)
        tr_file.close()
        return (read_fn, write_fn, read_data, read_hash)

    @staticmethod
    def make_test_dict(read_fn, write_fn, read_data, read_hash,
                       host_path, cntr_path):
        return {'read_fn': read_fn, 'write_fn': write_fn,
                'read_data': read_data, 'read_hash': read_hash,
                'write_hash': None,  # Filled in after execute()
                'host_path': host_path, 'cntr_path': cntr_path}

    def init_path_info(self, path_info, host_paths, cntr_paths, tmpdir):
        if host_paths is None or len(host_paths) < 1:
            raise DockerTestNAError("Configuration options host_paths and "
                                    "cntr_paths CSV lists are empty")
        if len(host_paths) != len(cntr_paths):
            raise DockerTestError("Configuration option host_paths CSV list "
                                  "must exactly match length of cntr_paths. "
                                  "'%s' != '%s'" % (host_paths, cntr_paths))
        # create template-substitution dicts for each container
        for host_path, cntr_path in zip(host_paths, cntr_paths):
            abs_host_path = os.path.abspath(host_path)
            # check for a valid host path for the test
            msg_pfx = "Configured host_path '%s' is not a "
            if not os.path.isdir(abs_host_path):
                raise DockerTestError(str(msg_pfx + "directory.") % host_path)
            if not os.path.ismount(abs_host_path):
                raise DockerTestError(str(msg_pfx + "mount point") % host_path)
            # Creation will raise OSError if not unique
            host_path = os.path.join(host_path, os.path.basename(self.tmpdir))
            os.mkdir(host_path)
            # keys must coorespond with those used in *_template strings
            args = self.make_test_files(host_path)
            # Inexplicable: pylint 1.7.1 (F26) can't grok '+= (host,cntr)'
            args += (host_path)
            args += (cntr_path)
            # list of dicts {'read_fn', 'write_fn', 'read_data', ...}
            test_dict = self.make_test_dict(*args)
            # unique cidfile for each container
            hpr = host_path.replace('/', '@')
            uniq = os.path.join(tmpdir,
                                hpr,
                                'cidfile')
            os.makedirs(os.path.join(tmpdir, hpr))
            test_dict['cidfile'] = uniq
            path_info.append(test_dict)

    @staticmethod
    def set_selinux_context(subtest, host_path):
        context = subtest.config['selinux_context'].strip()
        if context != '':
            environment.set_selinux_context(host_path, context)

    @staticmethod
    def make_dockercmd(subtest, dockercmd_class, fqin,
                       run_template, cmd_tmplate, test_dict):
        # safe_substutute ignores unknown tokens
        subargs = get_as_list(str(run_template % test_dict))
        subargs.append(fqin)
        subargs.append(cmd_tmplate % test_dict)
        return dockercmd_class(subtest, 'run', subargs)

    @staticmethod
    def init_dkrcmds(subtest, path_info, dockercmds):
        run_template = subtest.config['run_template']
        cmd_tmplate = subtest.config['cmd_template']
        fqin = DockerImage.full_name_from_defaults(subtest.config)
        for test_dict in path_info:
            dockercmds.append(subtest.make_dockercmd(subtest,
                                                     DockerCmd,
                                                     fqin,
                                                     run_template,
                                                     cmd_tmplate,
                                                     test_dict))

    @staticmethod
    def try_kill(subtest, cidfilename, cmdresult):
        docker_containers = DockerContainers(subtest)
        try:
            cidfile = open(cidfilename, 'rb')
            cid = cidfile.read()
            if len(cid) < 12:
                raise ValueError()
            else:
                docker_containers.kill_container_by_long_id(cid.strip())
        except ValueError:
            subtest.logdebug("Container %s not found to kill", cid[:12])
        except IOError:
            subtest.logdebug("Container never ran for %s", cmdresult)

    @staticmethod
    def try_rm(subtest, cidfilename, cmdresult):
        docker_containers = DockerContainers(subtest)
        try:
            cidfile = open(cidfilename, 'rb')
            cid = cidfile.read()
            if len(cid) < 12:
                raise ValueError()
            docker_containers.remove_by_id(cid.strip())
            subtest.loginfo("Removed container %s", cid[:12])
        except ValueError:
            subtest.logdebug("Container %s not found to rm", cid[:12])
        except IOError:
            subtest.logdebug("Container never ran for %s", cmdresult)

    @staticmethod
    def cleanup_test_dict(subtest, path_info):
        for test_data in path_info:
            write_path = os.path.join(test_data['host_path'],
                                      test_data['write_fn'])
            read_path = os.path.join(test_data['host_path'],
                                     test_data['read_fn'])
            if write_path is not None and os.path.isfile(write_path):
                os.unlink(write_path)
                subtest.logdebug("Removed %s", write_path)
            if read_path is not None and os.path.isfile(read_path):
                os.unlink(read_path)
                subtest.logdebug("Removed %s", read_path)

    def cleanup_cntnrs(self):
        if self.config['remove_after_test']:
            cmdresults = self.sub_stuff.get('cmdresults', [])
            for index, cmdresult in enumerate(cmdresults):
                cidfilename = self.sub_stuff['path_info'][index]['cidfile']
                try:
                    self.try_kill(self, cidfilename, cmdresult)
                    self.try_rm(self, cidfilename, cmdresult)
                except ValueError, detail:
                    self.logwarning("Cleanup problem detected: ValueError: %s",
                                    str(detail))
                    continue


class volumes_rw(volumes_base):

    def initialize(self):
        super(volumes_rw, self).initialize()
        host_paths = get_as_list(self.config['host_paths'])
        cntr_paths = get_as_list(self.config['cntr_paths'])
        # list of substitution dictionaries for each container
        path_info = self.sub_stuff['path_info'] = []
        self.init_path_info(path_info, host_paths, cntr_paths, self.tmpdir)
        dockercmds = self.sub_stuff['dockercmds'] = []
        self.sub_stuff['cmdresults'] = []
        # Does not execute()
        self.init_dkrcmds(self, path_info, dockercmds)

    def run_once(self):
        super(volumes_rw, self).run_once()
        for dockercmd in self.sub_stuff['dockercmds']:
            # Also updates self.sub_stuff['cids']
            self.sub_stuff['cmdresults'].append(dockercmd.execute())
        for test_dict in self.sub_stuff['path_info']:
            host_path = test_dict['host_path']
            write_fn = test_dict['write_fn']
            try:
                write_path = os.path.join(host_path, write_fn)
                write_file = open(write_path, 'rb')
                data = write_file.read()
                # md5sum output format:  hash + ' ' + filename|-
                self.logdebug("Data read from %s: '%s'", write_path, data)
                test_dict['write_hash'] = data.strip().split(None, 1)[0]
            except (IOError, OSError, IndexError, AttributeError), xcept:
                self.logerror("Problem reading hash from output file: %s: "
                              "%s: %s",
                              write_path, xcept.__class__.__name__, xcept)

    def postprocess(self):
        super(volumes_rw, self).postprocess()
        results_data = zip(self.sub_stuff['cmdresults'],
                           self.sub_stuff['path_info'])
        for cmdresult, test_dict in results_data:
            self.failif_ne(cmdresult.exit_status, 0,
                           "Non-zero exit status: %s" % cmdresult)
            wh = test_dict['write_hash']
            rh = test_dict['read_hash']
            hp = test_dict['host_path']
            cp = test_dict['cntr_path']
            msg = ("Test hash mismatch for volume %s:%s; "
                   "Command result %s"
                   % (hp, cp, cmdresult))
            self.failif_ne(wh, rh, msg)

    def cleanup(self):
        self.cleanup_test_dict(self, self.sub_stuff['path_info'])
        self.cleanup_cntnrs()
        super(volumes_rw, self).cleanup()


class oci_umount(volumes_base):
    """
    oci-umount is a docker hook shipping in RHEL 7.4+. Its purpose is
    to unmount certain critical filesystems before the container starts.
    See rhbz#1470261

    This test runs a docker container with / and /var/lib/docker mounted,
    gets a list (via findmnt) of mounted filesystems in that container,
    and verifies that none of those are in the /etc/oci-umount.conf
    exclusion list.
    """

    def initialize(self):
        super(oci_umount, self).initialize()

        # Config file contains filesystem paths, one per line. It may
        # also contain comments or empty lines, both of which we ignore.
        should_not_be_mounted = []
        try:
            with open('/etc/oci-umount.conf', 'r') as oci_umount_conf:
                for line in oci_umount_conf:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        should_not_be_mounted.append(line)
        except IOError:
            raise DockerTestNAError("oci-umount not installed or configured")
        if not should_not_be_mounted:
            raise DockerTestNAError("oci-umount is disabled")
        self.stuff['should_not_be_mounted'] = should_not_be_mounted

    def run_once(self):
        super(oci_umount, self).run_once()
        fqin = DockerImage.full_name_from_defaults(self.config)
        dc = DockerCmd(self, 'run', ['--rm',
                                     '-v', '/:/rootfs',
                                     '-v', '/var/lib/docker:/var/lib/docker',
                                     fqin, 'findmnt -R -n --list /'])
        OutputGood(dc.execute())

        # Output is a list of (path, device, fstype, options).
        # We only care about the first field.
        self.stuff['mounted'] = []
        for line in dc.stdout.splitlines():
            (fs, _) = line.split(' ', 1)
            self.stuff['mounted'].append(fs)
        self.failif(len(self.stuff['mounted']) == 0,
                    'container reported no mounted filesystems')

    def postprocess(self):
        super(oci_umount, self).postprocess()
        missed = self.cross_check_mounts()
        self.failif_ne(missed, [], "filesystem(s) not unmounted by oci-umount")

    def cross_check_mounts(self):
        """
        Cross-checks two lists: actual mounted filesystems, and the
        oci-umount input list. Return a list of all mounted filesystems
        which contain a substring from the oci-umount list. (Should
        be an empty list).
        """
        did_not_umount = []
        for omit in self.stuff['should_not_be_mounted']:
            # Special wildcard case: '/foo/bar/*' means to unmount everything
            # under /foo/bar but leave /foo/bar itself. To test this we
            # simply strip off the star, leaving the trailing slash: this
            # triggers a test failure on /foo/bar/x but not /foo/bar.
            if omit.endswith('/*'):
                omit = omit.rstrip('*')

            for mounted in self.stuff['mounted']:
                if omit in mounted:
                    did_not_umount.append(mounted)
        return did_not_umount


class oci_umount_bz1472121(volumes_base):
    """
    Simple and hopefully temporary test for bz1472121, in which one
    particular volume-mount incantation triggers a segv in oci-umount.
    This test is being put into place 2017-07-20 just to make sure
    that all known docker builds include a fix. Once that is confirmed,
    and stable, we may be able to remove this test.
    """

    def initialize(self):
        super(oci_umount_bz1472121, self).initialize()
        self.failif(not os.path.exists('/etc/oci-umount.conf'),
                    "oci-umount not installed", DockerTestNAError)

    def run_once(self):
        super(oci_umount_bz1472121, self).run_once()
        fqin = DockerImage.full_name_from_defaults(self.config)
        bindmount = '/var/lib/docker/devicemapper'
        dc = DockerCmd(self, 'run', ['--rm',
                                     '-v', '%s:%s' % (bindmount, bindmount),
                                     fqin, 'true'])
        # On a system with faulty oci-umount, e.g. 1.12.6-47.git0fdc778.el7,
        # this will fail with "oci runtime error: ...error running hook:
        # signal: segmentation fault (core dumped)"
        OutputGood(dc.execute())
