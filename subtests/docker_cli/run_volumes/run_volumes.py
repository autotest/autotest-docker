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

import os.path
import hashlib
from autotest.client import utils
from dockertest.containers import DockerContainers
from dockertest.dockercmd import DockerCmd
from dockertest.images import DockerImage
from dockertest.subtest import SubSubtest
from dockertest.subtest import SubSubtestCaller
from dockertest.xceptions import DockerTestNAError
from dockertest import environment
from dockertest.config import get_as_list


class run_volumes(SubSubtestCaller):
    config_section = 'docker_cli/run_volumes'


class volumes_base(SubSubtest):

    @staticmethod
    def make_test_files(host_path):
        # Symlink can't be mountpoint (e.g. for NFS, SMB, etc.)
        if (not os.path.isdir(host_path) or
                os.path.islink(host_path)):
            raise DockerTestNAError('Configured path "%s" is a symlink '
                                    'or not a directory' % host_path)
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
        # create template-substitution dicts for each container
        for host_path, cntr_path in zip(host_paths, cntr_paths):
            # check for a valid host path for the test
            if not os.path.isdir(host_path):
                raise DockerTestNAError("Configured host_path '%s' is not a "
                                        "directory." % host_path)
            if not cntr_path or len(cntr_path) < 4:
                raise DockerTestNAError("Configured cntr_path '%s' is not a "
                                        "directory." % cntr_path)
            # keys must coorespond with those used in *_template strings
            args = self.make_test_files(os.path.abspath(host_path))
            args += (host_path, cntr_path)
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
        if len(host_paths) != len(cntr_paths):
            raise DockerTestNAError("Configuration option host_paths CSV list "
                                    "must exactly match length of cntr_paths. "
                                    "'%s' != '%s'" % (host_paths, cntr_paths))
        if len(host_paths) < 1:
            raise DockerTestNAError("Configuration options host_paths and "
                                    "cntr_paths CSV lists are empty")
        # list of substitution dictionaries for each container
        path_info = self.sub_stuff['path_info'] = []
        # Throws DockerTestNAError if any host_paths is bad
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
            self.failif(cmdresult.exit_status != 0,
                        "Non-zero exit status: %s" % cmdresult)
            wh = test_dict['write_hash']
            rh = test_dict['read_hash']
            hp = test_dict['host_path']
            cp = test_dict['cntr_path']
            msg = ("Test hash mismatch for volume %s:%s; "
                   "Expecting data %s, read data %s; "
                   "Command result %s"
                   # wh/rh order is backwards for readability
                   % (hp, cp, rh, wh, cmdresult))
            self.failif(wh != rh, msg)

    def cleanup(self):
        self.cleanup_test_dict(self, self.sub_stuff['path_info'])
        self.cleanup_cntnrs()
        super(volumes_rw, self).cleanup()
