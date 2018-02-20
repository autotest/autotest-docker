# DANGER: CONSTRUCTION-ZONE:

## Hard-hat, double-underwear, and dark-sunglasses required!

### Useful documentation has been stripped for your own safety

# Running doc^H^H^H^podman-autotest

    # cd /var/lib/autotest/client
    # unset XDG_RUNTIME_DIR             ! podman won't run if this is set
    # ./autotest-local run docker

This will take 25-35 minutes depending on the virt horsepower and
the version of podman (some earlier versions hang for a long time).


# Review results

Open ``/var/lib/autotest/client/results/default/job_report.html``

You will see a table of results, with poorly-chosen non-colorblind-friendly
green/red for GOOD/FAIL respectively. Click on the `Debug` link for any
result of interest.  You'll see a list of files
and have to click the right one.

Look for boldface red; that shows the actual failure. Sometimes the actual
error is in orange (warning), especially if you see 'Postprocess' in
orange. Those are magic tests that don't actually fail in the moment
and are hard to find. The `build` test is an example of this.

(Note that some orange warnings are OK and expected. Sorry, but you'll
have to ignore the smell for now.)

# Debugging results

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

# Rerunning tests

Use the ``--tag`` argument to avoid clobbering ``results/default``

    # cd /var/lib/autotest/client
    # ./autotest-local run --tag=nasty_junk docker

Then look under ``/var/lib/autotest/client/results/nasty_junk`` for
the mostly useless details.

If you want to run just one short subtest, use --args:

    virt# ./autotest-local run docker --args docker_cli/foobar
               (replace foobar with attach, images_all, build, etc)

Short subtests can finish in 1-3 minutes instead of 20. You can
use this to instrument the code (adding printfs) then reload
in your web browser to view results.

# Happy hacking, and please, please: do it alone.

Whatever stumbling block you run into, I've almost certainly already
encountered it, too bad for you. Don't ping me on IRC, or send me
email. I don't care, just --force merge your change here and
we'll all hope for the best.
