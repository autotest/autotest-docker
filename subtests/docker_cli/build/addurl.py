import os.path
import re
from build import BuildSubSubtest


class addurl(BuildSubSubtest):

    ADDURL_REGEX = re.compile(r'ADD\s+.*\.')

    def make_builds(self, source):
        std_build = super(addurl, self).make_builds(source)
        with_str = ('ADD %s %s'
                    % (self.config['fileurl'], self.config['filepath']))
        dockerfile_path = os.path.join(std_build[0].dockerfile_dir_path,
                                       'Dockerfile')
        self.dockerfile_replace_line(dockerfile_path,
                                     self.ADDURL_REGEX, with_str)
        return std_build
