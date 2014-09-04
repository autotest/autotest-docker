"""
This tests the `docker build --rm` feature + with the docker caching off
1. Create container using $part dockerfile (--rm=True)
2. Create container using $full dockerfile (--rm=False)
3. Check the number of created containers and images (part & full contain
the same basics but cache is disabled, all containers should be created)
"""
from rm_false import rm_false


class rm_false_nocache(rm_false):
    pass
