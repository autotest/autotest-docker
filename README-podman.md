Instructions for testing podman with docker-autotest
====================================================

2018-04-11 : This document describes how to set up docker-autotest
on a Fedora system, then run it against podman.

*This is a work in progress*. In particular, much of it is
crappy code intended solely to work around docker/podman
incompatibilities, some is debugging code intended for figuring
out real failures, and some is workarounds for ways in which
podman and docker will presumably forever differ. I (Ed) reserve
the right to force-push new commits to this branch without notice.

Set up a virt
-------------

I (Ed) have done all my testing on f27, but f28 is worth testing too.

Setting up the virt is left as an exercise for the reader. I suggest
creating one inside the Red Hat network: one of the `pulls` from
registry.access.redhat.com fails if run from outside, and you don't
want to waste time debugging that.


Configure it
------------

Check out this repo on a Fedora 27 host:

    $ cd /some/nice/directory/
    $ git clone --branch podman_fixes https://github.com/edsantiago/autotest-docker.git
    $ cd autotest-docker

Run this command:

    $ HOSTNAME=name-or-ip-address-of-your-virt
    $ ansible-playbook -i $HOSTNAME, setup-podman-autotest.yml -v
                                   ^--- do not omit the comma

(I suggest Fedora 27 because ansible is unreliably chaotic: things that
work on one version don't work on the next, and vice-versa. I do all
my development on f27 and am not interested in testing any of this on
RHEL or Fedora Rawhide; at least not until ansible calms down).
(Also: maybe there's some way to run the ansible stuff on the same
virt, using localhost or something. I dunno. That's not my M.O. so
I'm not going to spend any time trying it. If you like working that way,
and can give me exact instructions for doing so, please do and I
will update this doc)

This will take about 5 minutes and will leave your Fedora virt configured
to run docker-autotest. This command is safe to run on any system,
e.g. your laptop. It does not require root on the host nor does it
muck with the host system in any way, um, unless you screw up HOSTNAME.

Run docker-autotest
-------------------

Log in to your virt as `root`, then run:

    virt# cd /var/lib/autotest/client
    virt# unset XDG_RUNTIME_DIR             ! podman won't run if this is set
    virt# ./autotest-local run docker

This will take 25-35 minutes depending on the virt horsepower and
the version of podman (some earlier versions hang for a long time).


Install GreaseMonkey scripts
----------------------------

While docker-autotest is running, I strongly encourage you to install
my [docker-autotest-highlight](https://gitlab.cee.redhat.com/greasemonkey/docker-autotest-highlight)
and [docker-autotest-job-report](https://gitlab.cee.redhat.com/greasemonkey/docker-autotest-job-report) GreaseMonkey scripts. (You only need to do this once).

They are not mandatory, but it would be insane to try to read
docker-autotest results without them. docker-autotest results
are horrible and unreadable; these tools make them somewhat less so.
Seriously: you will be in a world of hurt if you try to read
docker-autotest results without these.

I'm not quite sure how to install into GM, honestly, but try these
direct links and lmk if they work:
[docker-autotest-highlight](https://gitlab.cee.redhat.com/greasemonkey/docker-autotest-highlight/raw/master/docker-autotest-highlight.user.js),
[docker-autotest-job-report](https://gitlab.cee.redhat.com/greasemonkey/docker-autotest-job-report/raw/master/docker-autotest-job-report.user.js).

This should download the scriptlet, and GM will ask for confirmation.
Please let me know if that works (or doesn't), and please help me
improve this documentation.
(Installing GreaseMonkey is left as an exercise for the reader).


Review results
--------------

Point your web browser at `http://IP-ADDRESS-OF-VIRT/default/job_report.html`

You will see a table of results, with poorly-chosen non-colorblind-friendly
green/red for GOOD/FAIL respectively. Click on the `Debug` link for any
result of interest: if you installed `docker-autotest-job-report`, this
takes you straight to the debug log; otherwise, you see a list of files
and have to click the right one. Sorry, I can't remember which one and
can't be bothered to check -- again, I recommend installing my GM scripts.

Look for boldface red; that shows the actual failure. Sometimes the actual
error is in orange (warning), especially if you see 'Postprocess' in
orange. Those are magic tests that don't actually fail in the moment
and are hard to find. The `build` test is an example of this.

(Note that some orange warnings are OK and expected. Sorry, but you'll
have to develop a sense for these yourself.)

Debugging results
-----------------

This is a nightmare.

Find the source code of the test: for a given test `foo` it will
be under `subtests/docker_cli/foo/` but there may be many files
in there - often it might be `foo.py` but it could also be
`subsubtestname.py` for a given subsubtest. Or, for a kill-related
test, `kill_utils.py`

In the py file, the sequence is:

    initialize()
    run_once()
    postprocess()

It can be hard to know exactly what is failing or why. My usual
process is to look in the web browser for **boldface**; this
indicates the docker commands being run. I'll see if I can
figure out what's going on just by looking at the docker commands.
Most of the time I can't, and I have to delve into the source
code. Here, again, you're on your own. Each subtest is an
unhappy family in its own unique way, and there's not really
any way I can prepare you for debugging any particular
failing test. Sorry.

Also note that I've already picked off the low-hanging fruit: any
subtest that can be easily figured out, I've already filed podman
issues for. The remaining failures are the hard ones, those that
are not immediately obvious from the debug log, and require
delving deep into the code. Again -- sorry.

Rerunning tests
---------------

First: *save your run*:

    virt# mv results/default results/$(date --iso-8601).01.full
                    (or .02.full or .03.foo-test or whatever)

This way you can revisit in your web browser.

If you want to run just one short subtest, use --args:

    virt# ./autotest-local run docker --args docker_cli/foobar
               (replace foobar with attach, images_all, build, etc)

Short subtests can finish in 1-3 minutes instead of 20. You can
use this to instrument the code (adding printfs) then reload
in your web browser to view results.

Happy hacking. And please, please: don't do it alone. Whatever
stumbling block you run into, I've almost certainly already
encountered. Ping me (esm) on IRC, or send me email. Even if you
cost me three minutes, it's in order to save you thirty. It's worth it.
