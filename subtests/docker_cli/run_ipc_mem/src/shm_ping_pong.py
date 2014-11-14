#!/usr/bin/env python
"""
This code attaches the $key shm memory, sets the value to $set_str and waits
until the $wait_for_str is set. Than it repeats the same $no_iter times.
"""
import ctypes
import sys
import time


IPC_CREAT = 01000
IPC_RMID = 0


class LazyPrinter(object):

    """
    Print only once per interval, skip messages in between.
    """

    def __init__(self, interval):
        self.timeout = None
        self.interval = interval
        self.msg = None
        self.changed = False

    @staticmethod
    def _log(msg):
        print msg
        sys.stdout.flush()

    def log(self, msg):
        if msg != self.msg:
            self.changed |= True
        if time.time() > self.timeout:
            if self.changed:
                self._log("--< SKIPPED LINES >--")
                self.changed = False
            self._log(msg)
            self.timeout = time.time() + self.interval
        self.msg = msg

    def forcelog(self):
        self._log(self.msg)


if len(sys.argv) != 6:
    raise ValueError("Usage: $script $key $no_iter $wait_for_str $set_str "
                     "$last")

# Load the libs from various locations...
for lib in ('libc.so.6', 'libc.so', './libc.so.x86_64', './libc.so.i686'):
    try:
        libc = ctypes.CDLL(lib)
        break
    except OSError:
        pass
else:
    sys.stdout.flush()
    raise OSError("Unable to load libc library")

for lib in ('librt.so.1', 'librt.so', './librt.so.x86_64', './librt.so.i686'):
    try:
        rt = ctypes.CDLL(lib)
        break
    except OSError:
        pass
else:
    sys.stdout.flush()
    raise OSError("Unable to load librt library")

shm_key = int(sys.argv[1])
no_iter = int(sys.argv[2])
length = 1024
shmid = rt.shmget(shm_key, length, 0644 | IPC_CREAT)
if shmid < 0:
    raise ValueError("Can't acces the %s shm" % shm_key)

log = LazyPrinter(1)
print "shmid = %s (%s)" % (shmid, shm_key)
sys.stdout.flush()
rt.shmat.restype = ctypes.c_void_p
addr = rt.shmat(shmid, 0, 0)
print "addr = %s" % addr
sys.stdout.flush()
if addr < 0:
    raise IOError("Incorrect addr %s" % addr)

string = (ctypes.c_char * length).from_address(addr)
print "content = %s" % string.value
sys.stdout.flush()
print "Silent 0th iteration..."
sys.stdout.flush()
wait_for_str = sys.argv[3]
set_str = sys.argv[4]
string.value = set_str
while string.value != wait_for_str:
    pass
for i in xrange(no_iter):
    while string.value != wait_for_str:
        log.log("%s: Waiting for %s (%s)" % (i, wait_for_str, string.value))
    string.value = set_str

log.forcelog()

if sys.argv[5] == 'y':
    print "Closing %s" % shmid
    sys.stdout.flush()
    rt.shmdt(addr)
    rt.shmctl(shmid, IPC_RMID, None)

print "All iterations passed"
sys.stdout.flush()
