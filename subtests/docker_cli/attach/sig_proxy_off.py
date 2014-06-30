"""
Test attach

1) Start docker run --interactive --name=xxx fedora trap signal
        command should wait to the trap signal.
2) Start docker attach --sig-proxy=false
3) Try to send signal to container process over attached docker
4) Check if docker process is still alive.
"""

from attach import sig_proxy_off_base

class sig_proxy_off(sig_proxy_off_base):
    pass
