from unittest2 import TestCase, main        # pylint: disable=unused-import
from mock import Mock
import autotest  # pylint: disable=unused-import
import inspect_keys
import json


class TestFilterKeys(TestCase):
    def _run_one_test(self, spec):
        """
        Helper for running an individual test.
        spec is a multi-line string containing specially-formed JSON.
        The parsing rule is: by default, the expected result is the
        same as the input. But if the '|' (pipe) character appears
        on the line, we treat it that line as having a left- and
        right-hand side. The left is our input JSON, the right is
        the expected JSON after filtering. Most of the time the
        right-hand side will be blank, indicating removed keys,
        but it may also be used for keys/values that change names.
        """
        mockself = Mock(spec=inspect_keys.inspect_keys)

        lhs = ''              # left-hand side: our original json
        rhs = ''              # right-hand side: what we expect from filter
        for line in spec.split("\n"):
            divider = line.find(' |')
            if divider >= 0:
                lhs += line[:divider - 1] + "\n"
                rhs += line[divider + 2:] + "\n"
            else:
                lhs += line + "\n"
                rhs += line + "\n"

        actual = inspect_keys.inspect_keys.filter_keys(mockself,
                                                       json.loads(lhs))
        self.maxDiff = None
        self.assertEqual(actual, json.loads(rhs))

    def test_basic(self):
        """
        Very simple test; makes sure that .Config.Labels is removed
        """
        self._run_one_test("""
[
{
    "A": "B",
    "Config": {
       "Labels": { "a": [ "this gets deleted" ] },   | "Labels": {},
       "Other":  [ "this is preserved" ]
    }
}
]
""")

    def test_multi_net(self):
        """
        Multiple .NetworkSettings.Networks.xxx are renamed
        """
        self._run_one_test("""
[
{
    "NetworkSettings": {
        "Networks": {
            "bridge": {                  | "RenamedForTesting_bridge": {
                "EndpointID": "--preserved--"
            },
            "nextnet": {                 | "RenamedForTesting_nextnet": {
                "AnotherPreservedKey": "yep"
            },
            "yetanothernet": {           | "RenamedForTesting_yetanothernet": {
                "never": "mind"
            },
            "CamelCase": {               | "RenamedForTesting_CamelCase": {
                "never": "mind"
            }
        }
    }
}
]
""")

    def test_full(self):
        """
        Huge monster results, taken from a real-world instance.
        """
        self._run_one_test("""
[
{
    "Id": "ed3b9325177ccd70717d58885dbeb53255b52f200be1dd7e65221e5eb805113e",
    "Created": "2016-03-30T17:51:47.675978044Z",
    "Path": "tail",
    "Args": [
        "-n1",
        "/proc/1/cgroup"
    ],
    "State": {
        "Status": "exited",
        "Running": false,
        "Paused": false,
        "Restarting": false,
        "OOMKilled": false,
        "Dead": false,
        "Pid": 0,
        "ExitCode": 0,
        "Error": "",
        "StartedAt": "2016-03-30T17:51:49.006872458Z",
        "FinishedAt": "2016-03-30T17:51:49.025916776Z"
    },
    "Image": "bf63a676257aeb7a....8f9b399004ef",
    "ResolvConfPath": "/var/lib/docker/containers/..../resolv.conf",
    "HostnamePath": "/var/lib/docker/containers/..../hostname",
    "HostsPath": "/var/lib/docker/containers/..../hosts",
    "LogPath": "/var/lib/docker/containers/..../....-json.log",
    "Name": "/modest_colden",
    "RestartCount": 0,
    "Driver": "devicemapper",
    "ExecDriver": "native-0.2",
    "MountLabel": "system_u:object_r:svirt_sandbox_file_t:s0:c3,c28",
    "ProcessLabel": "system_u:system_r:svirt_lxc_net_t:s0:c3,c28",
        "AppArmorProfile": "",
    "ExecIDs": null,
    "HostConfig": {
        "Binds": null,
        "ContainerIDFile": "",
        "LxcConf": [],
        "Memory": 0,
        "MemoryReservation": 0,
        "MemorySwap": 0,
        "KernelMemory": 0,
        "CpuShares": 0,
        "CpuPeriod": 0,
        "CpusetCpus": "",
        "CpusetMems": "",
        "CpuQuota": 0,
        "BlkioWeight": 0,
        "OomKillDisable": false,
        "MemorySwappiness": -1,
        "Privileged": false,
        "PortBindings": {},
        "Links": null,
        "PublishAllPorts": false,
        "Dns": [],
        "DnsOptions": [],
        "DnsSearch": [],
        "ExtraHosts": null,
        "VolumesFrom": null,
        "Devices": [],
        "NetworkMode": "default",
        "IpcMode": "",
        "PidMode": "",
        "UTSMode": "",
        "CapAdd": null,
        "CapDrop": null,
        "GroupAdd": null,
        "RestartPolicy": {
            "Name": "no",
            "MaximumRetryCount": 0
        },
        "SecurityOpt": null,
        "ReadonlyRootfs": false,
        "Ulimits": null,
        "LogConfig": {
            "Type": "json-file",
            "Config": {}
        },
        "CgroupParent": "foo.slice",
        "ConsoleSize": [
            0,
            0
        ],
        "VolumeDriver": "",
        "ShmSize": 67108864
    },
    "GraphDriver": {
        "Name": "devicemapper",
        "Data": {
            "DeviceId": "2310",
            "DeviceName": "docker-253:3-....",
            "DeviceSize": "107374182400"
        }
    },
    "Mounts": [],
    "Config": {
        "Hostname": "ed3b9325177c",
        "Domainname": "",
        "User": "",
        "AttachStdin": true,
        "AttachStdout": true,
        "AttachStderr": true,
        "Tty": true,
        "OpenStdin": true,
        "StdinOnce": true,
        "Env": [
            "container=docker",
            "PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin"
        ],
        "Cmd": [
            "tail",
            "-n1",
            "/proc/1/cgroup"
        ],
        "Image": "rhel7/rhel:latest",
        "Volumes": null,
        "WorkingDir": "",
        "Entrypoint": null,
        "OnBuild": null,
        "Labels": {
            "Architecture": "x86_64",                                 |
            "Authoritative_Registry": "registry.access.redhat.com",   |
            "BZComponent": "rhel-server-docker",                      |
            "Build_Host": "rcm-img02.build.eng.bos.redhat.com",       |
            "Name": "rhel7/rhel",                                     |
            "Release": "46",                                          |
            "Vendor": "Red Hat, Inc.",                                |
            "Version": "7.2"                                          |
        },
        "StopSignal": "SIGTERM"
    },
    "NetworkSettings": {
        "Bridge": "",
        "SandboxID": "",
        "HairpinMode": false,
        "LinkLocalIPv6Address": "",
        "LinkLocalIPv6PrefixLen": 0,
        "Ports": null,
        "SandboxKey": "",
        "SecondaryIPAddresses": null,
        "SecondaryIPv6Addresses": null,
        "EndpointID": "",
        "Gateway": "",
        "GlobalIPv6Address": "",
        "GlobalIPv6PrefixLen": 0,
        "IPAddress": "",
        "IPPrefixLen": 0,
        "IPv6Gateway": "",
        "MacAddress": "",
        "Networks": {
            "bridge": {                    | "RenamedForTesting_bridge": {
                "EndpointID": "",
                "Gateway": "",
                "IPAddress": "",
                "IPPrefixLen": 0,
                "IPv6Gateway": "",
                "GlobalIPv6Address": "",
                "GlobalIPv6PrefixLen": 0,
                "MacAddress": ""
            }
        }
    }
}
]
""")

    def test_meta(self):
        """
        Make sure the above tests aren't just NOPing.
        """
        raised = False
        try:
            self._run_one_test("""
[
{
    "This":"Should"         | "Cause": "A Test Failure"
}
]
""")
        except AssertionError:
            raised = True
        if not raised:
            self.fail("Known-bad test did not raise exception.")

if __name__ == '__main__':
    main()
