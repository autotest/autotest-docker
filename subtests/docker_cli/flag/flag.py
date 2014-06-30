"""
Test should not accepts all/most of the flags which don't raise any
exception, don't log any message and are silently ignored.

1. Run a container with flags which doesn't make sense
2. Check the error/usage in docker run ouput
3. Test will FAIL if the container could be run.
"""

from dockertest import subtest
from dockertest.dockercmd import DockerCmd
from dockertest.dockercmd import MustFailDockerCmd
from dockertest.images import DockerImage
from dockertest.containers import DockerContainers


class flag(subtest.Subtest):
    config_section = "docker_cli/flag"

    def initialize(self):
        super(flag, self).initialize()
        self.stuff["containter_name"] = []
        self.stuff["subargs"] = []
        self.stuff["cmdresult"] = []
        docker_containers = DockerContainers(self)
        self.logdebug("Generating ramdom name will take 1 minute")
        cname = docker_containers.get_unique_name("docker", "test", 4)
        self.stuff["containter_name"] = cname

    def run_once(self):
        super(flag, self).run_once()
        args = ["run"]
        args.append("--name=%s" % self.stuff["containter_name"])
        fin = DockerImage.full_name_from_defaults(self.config)
        args.append(fin)
        args.append("/bin/bash")
        args.append("-c")
        args.append("\"echo negative test for docker flags\"")
        dc = MustFailDockerCmd(self, self.config["flag_args"], args)
        self.stuff["cmdresult"] = dc.execute()

    def postprocess(self):
        super(flag, self).postprocess()
        stderr = self.stuff['cmdresult'].stderr
        # searched_info is warning/error/usage output like what we expected
        searched_info = self.config["searched_info"]
        self.logdebug("Verifying expected '%s' is in stderr", searched_info)
        # when exit code!=0, it'll fail if the info expected is not in stderr
        self.failif(searched_info not in stderr, "The output expected '%s'"
                    "not found in the docker output: %s"
                    % (searched_info, stderr))

    def cleanup(self):
        super(flag, self).cleanup()
        if self.config["remove_after_test"]:
            dkrcmd = DockerCmd(self, "rm", [self.stuff["containter_name"]])
            dkrcmd.execute()
