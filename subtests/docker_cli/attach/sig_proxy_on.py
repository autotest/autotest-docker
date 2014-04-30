"""
Test attach

1) Start docker run --interactive --name=xxx fedora trap signal
        command should wait to the trap signal.
2) Start docker attach --sig-proxy=true
3) Try to send signal to container process over attached docker
4) Check if docker process died on signal.
"""
# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103

from attach import sig_proxy_off_base, attach_base
from dockertest.output import OutputGood


class sig_proxy_on(sig_proxy_off_base):
    def postprocess(self):
        super(attach_base, self).postprocess()  # Prints out basic info
        # Fail test if bad command or other stdout/stderr problems detected

        OutputGood(self.sub_stuff['cmdresult'])

        c_name = self.sub_stuff["rand_name"]
        containers = self.sub_stuff['cont'].list_containers_with_name(c_name)
        if containers:
            self.failif("Exited" not in containers[0].status,
                        "Docker command wasn't killed by attached docker when"
                        " sig-proxy=true. It shouldn't happened.")
        else:
            self.logerror("Unable to find started container.")
