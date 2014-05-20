"""
Test read & write to various host-paths as container volumes

1. Write unique value to file on host path
2. Start container, hash file, store has in second file
3. Check second file on host, verify hash matches.
"""

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

import time
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

    @staticmethod
    def init_path_info(path_info, host_paths, cntr_paths, tmpdir):
        # create template-substitution dicts for each container
        for host_path, cntr_path in zip(host_paths, cntr_paths):
            # check for a valid host path for the test
            if not os.path.isdir(host_path):
                raise DockerTestNAError("Configured host_path '%s' invalid."
                                        % host_path)
            if not cntr_path or len(cntr_path) < 4:
                raise DockerTestNAError("Configured cntr_path '%s' invalid."
                                        % cntr_path)
            # keys must coorespond with those used in *_template strings
            args = volumes_base.make_test_files(os.path.abspath(host_path))
            args += (host_path, cntr_path)
            # list of dicts {'read_fn', 'write_fn', 'read_data', ...}
            test_dict = volumes_base.make_test_dict(*args)
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
        subargs = str(run_template % test_dict).strip().split(',')
        subargs.append(fqin)
        subargs.append(cmd_tmplate % test_dict)
        return dockercmd_class(subtest.parent_subtest, 'run', subargs)

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

class volumes_rw(volumes_base):

    def initialize(self):
        super(volumes_rw, self).initialize()
        host_paths = self.config['host_paths'].strip().split(',')
        cntr_paths = self.config['cntr_paths'].strip().split(',')
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
        # Does not execute()
        self.init_dkrcmds(self, path_info, dockercmds)
        self.sub_stuff['cmdresults'] = []
        self.sub_stuff['cids'] = []

    def run_once(self):
        super(volumes_rw, self).run_once()
        for dockercmd in self.sub_stuff['dockercmds']:
            # Also updates self.sub_stuff['cids']
            self.sub_stuff['cmdresults'].append(dockercmd.execute())
        wait_stop = self.config['wait_stop']
        self.loginfo("Waiting %d seconds for docker to catch up", wait_stop)
        time.sleep(wait_stop)
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
                self.logerror("Problem reading hash from output file: %s: %s",
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
        super(volumes_rw, self).cleanup()
        if self.config['remove_after_test']:
            if self.sub_stuff.get('cmdresults') is None:
                self.logdebug("No commands ran, nothing to clean up")
                return  # no commands ran
            for index, cmdresult in enumerate(self.sub_stuff['cmdresults']):
                cidfilename = self.sub_stuff['path_info'][index]['cidfile']
                try:
                    self.try_kill(self.parent_subtest, cidfilename, cmdresult)
                    self.try_rm(self.parent_subtest, cidfilename, cmdresult)
                except ValueError, detail:
                    self.logwarning("Cleanup problem detected: ValueError: %s",
                                    str(detail))
                    continue
            for test_data in self.sub_stuff['path_info']:
                write_path = os.path.join(test_data['host_path'],
                                          test_data['write_fn'])
                read_path = os.path.join(test_data['host_path'],
                                         test_data['read_fn'])
                if write_path is not None and os.path.isfile(write_path):
                    os.unlink(write_path)
                    self.logdebug("Removed %s", write_path)
                if read_path is not None and os.path.isfile(read_path):
                    os.unlink(read_path)
                    self.logdebug("Removed %s", read_path)
