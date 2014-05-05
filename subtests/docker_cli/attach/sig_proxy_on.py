"""
Test attach

1) Start docker run --interactive --name=xxx fedora trap signal
        command should wait to the trap signal.
2) Start docker attach --sig-proxy=true
3) Try to send signal to container process over attached docker
4) Check if docker process died on signal.
"""
from attach import sig_proxy_off_base

class sig_proxy_on(sig_proxy_off_base):

    def check_containers(self, containers):
        if containers:
            self.failif("Exited" not in containers[0].status,
                        "Docker command wasn't killed by attached docker when"
                        " sig-proxy=true. It shouldn't happened.")
        else:
            self.logerror("Unable to find started container.")
