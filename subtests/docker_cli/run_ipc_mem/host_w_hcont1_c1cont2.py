"""
1. start cont1 --ipc host and worker (cont1 allocates the shm)
2. start cont2 --ipc container:$cont1
3. start workers on host and cont2
4. wait until they finish
"""
import random

from run_ipc_mem import IpcBase


class host_w_hcont1_c1cont2(IpcBase):

    def run_once(self):
        super(host_w_hcont1_c1cont2, self).run_once()
        no_iter = self.config.get('no_iterations', 1024)
        key = self._find_hosts_free_ipc(random.randint(1, 65536))
        self.sub_stuff['shms'].append(key)
        str1 = 'a%s' % self._generate_string()
        str2 = 'b%s' % self._generate_string()
        str3 = 'c%s' % self._generate_string()
        # start containers
        c1_name = self._init_container_stdin('cont1', "host")
        self._init_container_stdin('cont2', "container:%s" % c1_name)
        # start worker on 3rd container
        args = "%s %s %s %s n" % (key, no_iter, str1, str2)
        self._exec_container_stdin(self.sub_stuff['cmds'][0], args)
        args = "%s %s %s %s n" % (key, no_iter, str2, str3)
        self._exec_host('host', args)
        args = "%s %s %s %s y" % (key, no_iter, str3, str1)
        self._exec_container_stdin(self.sub_stuff['cmds'][1], args)

    def postprocess(self):
        super(host_w_hcont1_c1cont2, self).postprocess()
        timeout = self.parent_subtest.adjust_timeout(120)
        self.sub_stuff['cmds'][1].wait_check(timeout)
        timeout = self.parent_subtest.adjust_timeout(15)
        self.sub_stuff['cmds'][2].wait_check(timeout)
        timeout = self.parent_subtest.adjust_timeout(15)
        self.sub_stuff['cmds'][0].wait_check(timeout)
        self.sub_stuff['cmds'] = []
        self.sub_stuff['shms'] = []
