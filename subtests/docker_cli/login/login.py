r"""
Summary
-------

Test variations of 'docker login'

Operational Summary
-------------------

#. Create a self-signed SSL certificate
#. Generate a pseudorandom password
#. Generate htpasswd file with a test user and this password
#. Run a registry container using new certificate & credentials
#. Run individual subtests against this standard setup
"""

import os
from base64 import b64encode
import json
import urllib2
import time
from autotest.client import utils
from dockertest.containers import DockerContainers
from dockertest.images import DockerImages
from dockertest.subtest import SubSubtest
from dockertest.output import OutputGood
from dockertest.output import mustpass, mustfail
from dockertest.dockercmd import DockerCmd
from dockertest.xceptions import DockerTestFail
from dockertest import subtest


class login(subtest.SubSubtestCaller):

    """ SubSubtest caller """


class login_base(SubSubtest):

    """ login base class; performs common setup. """

    def initialize(self):
        super(login_base, self).initialize()

        # We need to create cert and htpasswd files for bind-mounting in
        # the registry container; do so in a safe temporary workdir.
        os.chdir(self.tmpdir)

        # Creates domain.crt and domain.key files
        self._create_certs()

        # Credentials: fixed username with pseudorandom password
        self._create_htpasswd()

        self._preserve_docker_auth_file()

        # Now run the registry itself, leave it running for the login test
        c_name = DockerContainers(self).get_unique_name()
        subargs = ['-d', '-p', '{port}:{port}'.format(**self.sub_stuff),
                   '--name', c_name,
                   '-v', '{}:/auth:Z'.format(self.tmpdir),
                   '-e', 'REGISTRY_HTTP_TLS_CERTIFICATE=/auth/domain.crt',
                   '-e', 'REGISTRY_HTTP_TLS_KEY=/auth/domain.key',
                   '-e', 'REGISTRY_AUTH=htpasswd',
                   '-e', 'REGISTRY_AUTH_HTPASSWD_REALM="Registry Realm"',
                   '-e', 'REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd',
                   self.config['registry_fqin']]
        self.sub_stuff['my_containers'] = [c_name]
        self.sub_stuff['my_images'] = []
        mustpass(DockerCmd(self, 'run', subargs).execute())
        self._wait_for_registry_ready()

    def _create_certs(self):
        """
        Create a self-signed SSL certificate for use by the registry
        container (registry auth only works with TLS).
        """
        localhost = 'localhost.localdomain'
        port = '5000'
        subj = '/C=US/ST=Foo/L=Bar/O=Red Hat, Inc./CN=%s' % localhost
        make_cert = ('openssl req -newkey rsa:4096 -nodes -sha256'
                     ' -keyout domain.key -x509 -days 2 -out domain.crt'
                     ' -subj "%s"' % subj)
        utils.run(make_cert, verbose=True)

        self.sub_stuff['localhost'] = localhost
        self.sub_stuff['port'] = port
        self.sub_stuff['server'] = localhost + ':' + port

    def _create_htpasswd(self):
        """
        Write an htpasswd file in our current directory, for use by
        the registry container (via bind mount). Use the registry image
        itself to run htpasswd, with -n so output goes to stdout, then
        capture that stdout and write it to a file in our current directory.
        """
        self.sub_stuff['user'] = 'testuser'
        self.sub_stuff['passwd'] = utils.generate_random_string(12)

        registry_fqin = self.config['registry_fqin']
        subargs = ['--rm', '--entrypoint', 'htpasswd', registry_fqin,
                   '-Bbn', self.sub_stuff['user'], self.sub_stuff['passwd']]
        htpasswd_cmdresult = DockerCmd(self, 'run', subargs).execute()
        with open('htpasswd', 'wb') as htpasswd_fh:
            htpasswd_fh.write(htpasswd_cmdresult.stdout)

    def _preserve_docker_auth_file(self):
        """
        docker login creates/overwrites a standard file; preserve it
        if it already exists.
        """
        auth_file = self.config['docker_auth_file']
        if not os.path.exists(auth_file):
            return
        saved_path = auth_file + '.PRESERVED'
        os.rename(auth_file, saved_path)
        self.sub_stuff['docker_auth_file_preserved'] = saved_path

    def _restore_docker_auth_file(self):
        """
        Restore previous docker auth file, if any. Otherwise, remove.
        """
        auth_file = self.config['docker_auth_file']
        key = 'docker_auth_file_preserved'
        if key in self.sub_stuff:
            os.rename(self.sub_stuff[key], auth_file)
        elif os.path.exists(auth_file):
            os.unlink(auth_file)

    def _wait_for_registry_ready(self, timeout=None):
        """
        Registry container takes some time to spin up and be ready. This
        can take a few seconds, and we don't want to run login commands
        before it's ready. We can't just connect to the port, because
        docker opens it immediately. Best solution seems to be to GET
        a well-defined v2 URL in the registry. It will fail with SSLEOF
        at the beginning, then fail with HTTP 401 (Unauthorized). Once
        we get that, trust that it's ready for login.
        """
        if timeout is None:
            timeout = self.config['wait_for_registry_ready']

        url = "https://{server}/v2/".format(**self.sub_stuff)
        end_time = time.time() + timeout
        while time.time() <= end_time:
            try:
                urllib2.urlopen(url)
            except urllib2.HTTPError as e:
                if e.reason == 'Unauthorized':
                    return
            except urllib2.URLError as e:
                # Likely case: registry is still spinning up. Keep waiting.
                pass
            time.sleep(0.5)
        raise DockerTestFail("timed out waiting for registry")

    def docker_login(self, password=None):
        """
        Run docker login against our local registry, using the supplied
        password (default: correct password for our setup).
        """
        if password is None:
            password = self.sub_stuff['passwd']
        # FIXME: --email option is deprecated in 1.12, and will be
        # removed in 1.13. We still need it for <= 1.10; otherwise
        # docker prompts from stdin, and we hang.
        dc = DockerCmd(self, 'login', ['--username', self.sub_stuff['user'],
                                       '--password', password,
                                       '--email', 'nobody@redhat.com',
                                       self.sub_stuff['server']])
        return dc.execute()

    def _check_credentials(self):
        """
        Examine saved credentials in docker auth file.
        If this is a logout test, make sure the server key is absent.
        Otherwise, make sure there's an auth entry for this server,
        and its value contains the expected username + password.
        """
        auth_file = self.config['docker_auth_file']
        fp = open(auth_file, 'rb')
        creds = json.load(fp)
        server = self.sub_stuff['server']

        # Use test name to determine whether cred should be present or not
        if 'logout' in self.__class__.__name__:
            self.failif(server in creds['auths'],
                        ('"%s" should not be in %s after docker logout'
                         % (server, auth_file)))
        else:
            # Stored credentials
            cred_hash = creds['auths'][server]['auth']
            # ...simply a base64-encoded('username:password'), see:
            #  https://coreos.com/os/docs/latest/registry-authentication.html
            expected = b64encode('{user}:{passwd}'.format(**self.sub_stuff))
            self.failif_ne(cred_hash, expected,
                           'saved credentials in %s' % auth_file)

    def docker_push(self, img_name, tag_name):
        """
        Run docker tag, then docker push against our local registry.
        Tag should always succeed but make no assumptions about push.
        """
        push_image = self.config['push_image']
        dc = DockerCmd(self, 'pull', [push_image])
        mustpass(dc.execute())
        self.sub_stuff['my_images'] += [push_image]

        self.sub_stuff['img_name'] = img_name
        self.sub_stuff['tag_name'] = tag_name
        pushed_name = ('{server}/{img_name}:{tag_name}'
                       .format(**self.sub_stuff))
        dc = DockerCmd(self, 'tag', [push_image, pushed_name])
        mustpass(dc.execute())
        self.sub_stuff['my_images'] += [pushed_name]

        return DockerCmd(self, 'push', [pushed_name]).execute()

    def cleanup(self):
        DockerContainers(self).clean_all(self.sub_stuff['my_containers'])
        DockerImages(self).clean_all(self.sub_stuff['my_images'])
        self._restore_docker_auth_file()


class login_ok(login_base):

    """
    1. Run 'docker login' with correct password
    2. Verify zero (success) exit status, and 'Login Succeeded' in stdout
    """

    def run_once(self):
        super(login_ok, self).run_once()
        self.sub_stuff["cmdresult"] = self.docker_login()

    def postprocess(self):
        super(login_ok, self).postprocess()
        cmdresult = self.sub_stuff['cmdresult']
        OutputGood(cmdresult)
        mustpass(cmdresult)
        self.failif_not_in("Login Succeeded", cmdresult.stdout,
                           "stdout from docker login")
        self._check_credentials()


class login_fail(login_base):

    """
    1. Run 'docker login' with incorrect password
    2. Verify error exit status, and reason in stderr
    """

    def run_once(self):
        super(login_fail, self).run_once()

        wrong_passwd = '!' + self.sub_stuff['passwd']
        self.sub_stuff["cmdresult"] = self.docker_login(wrong_passwd)

    def postprocess(self):
        super(login_fail, self).postprocess()
        cmdresult = self.sub_stuff['cmdresult']
        OutputGood(cmdresult, ignore_error=True)
        mustfail(cmdresult, 1)
        self.failif_not_in("401 Unauthorized", cmdresult.stderr,
                           "stderr from failed docker login")


class logout_ok(login_ok):

    """
    1. Run the login_ok test
    2. Run docker logout
    3. Make sure stored credentials are removed
    4. Make sure stdout contains a logout message
    """

    def run_once(self):
        super(logout_ok, self).run_once()
        logout = DockerCmd(self, 'logout', [self.sub_stuff['server']])
        self.sub_stuff['cmdresult_logout'] = logout.execute()

    def postprocess(self):
        super(logout_ok, self).postprocess()
        self.failif_not_in('Remove login credentials for',
                           self.sub_stuff['cmdresult_logout'].stdout,
                           'stdout from docker logout')


class push_ok(login_base):

    """
    1. Run 'docker login' with correct password
    2. Run 'docker tag', then 'docker push' to the new local registry
    3. Verify zero (success) exit status, and 'Pushed' in stdout
    """

    def run_once(self):
        super(push_ok, self).run_once()
        self.docker_login()
        self.sub_stuff['pushresult'] = self.docker_push('push_ok', 'tag_ok')

    def postprocess(self):
        super(push_ok, self).postprocess()
        cmdresult = self.sub_stuff['pushresult']
        OutputGood(cmdresult)
        mustpass(cmdresult)
        self.failif_not_in(": Pushed", cmdresult.stdout,
                           "stdout from docker push")
        self.failif_not_in("tag_ok: digest:", cmdresult.stdout,
                           "stdout from docker push")


class push_fail(login_base):

    """
    1. Run 'docker login' with incorrect password
    2. Run 'docker tag', then 'docker push' to the new local registry
    3. Verify error exit status
    """

    def run_once(self):
        super(push_fail, self).run_once()
        self.docker_login('!' + self.sub_stuff['passwd'])
        self.sub_stuff['pushresult'] = self.docker_push('push_fail', 'tag_x')

    def postprocess(self):
        super(push_fail, self).postprocess()
        cmdresult = self.sub_stuff['pushresult']
        OutputGood(cmdresult, ignore_error=True)
        mustfail(cmdresult, 1)
