# OPERATIONS -- how this pipeline reaches its compute

No credential value appears in this file, in this package, or in any file
produced by it.

## Environment variables

The remote runner (`_tools/rsc.py`) reads exactly four values from the
environment:

    CIS_HOST   pod hostname
    CIS_PORT   ssh port
    CIS_USER   ssh user
    CIS_PASS   ssh password            <- never written to any file

All three of HOST, PORT and PASS are **required**: none has a compiled-in
default. A default that survives in a shipped file is half of a
retired endpoint (the port one did, until C-248). USER alone keeps
a default -- an account points at nobody's host.

`rsc.py` in this package has **no compiled-in defaults** for `CIS_HOST` or
`CIS_PASS`; it reads them from the environment and fails loudly if absent. An
earlier revision carried both as defaults.

Since 2026-09-25 that is enforced by the packager rather than by the re-cut: it
rewrites the shipped copy and then re-reads it off disk, refusing the build if any
of `CIS_HOST`, `CIS_PORT`, `CIS_PASS` can still fall back to a compiled-in value,
or if the live credential appears anywhere in the package. The rewritten file is
byte-identical to the one rc4 shipped (`ec2bfa48f584db8a`), so the form is the
same -- it is now produced by a rule instead of by a patch.

An earlier revision of the package also carried `code/_tools/.rsc_cache.json`,
a runtime cache naming the pod endpoint. It was a dotfile, so no exclusion table
caught it. It is now excluded by class -- see `ERRATA.md` section 2.

## Two carriers, two different precedences -- do not mix them up

    CIS_HOST / CIS_PORT / CIS_USER : set by `_tools/watchdog.cmd` via `set`
                                     -> the SCRIPT wins; editing the user-level registry
                                        value has NO effect for runs launched by that script
    CIS_PASS                       : NOT set by the script (deliberately)
                                     -> only the user-level environment (`HKCU\Environment`)
                                        supplies it; editing the script has NO effect

Consequence: when retargeting the pod you must change **the script for
host/port** and **the registry for the password**. Changing only one of them
fails **silently** -- it looks like a network or credential outage.

## Judging whether the pod is up

**Do not judge it from an arbitrary shell.** A shell that lacks the four
variables makes `rsc.py` fail at the first SSH call, which is indistinguishable
from an unreachable pod if you only look at the exit code: `watchdog.cmd`
propagates the child's code, so "my shell had no environment" and "the pod is
down" both surface as `exit=1`. (Ledger C-242: measured, same pod, two minutes
apart -- `Authentication failed.` from a bare shell, `COMPUTE_OK (exit=0)` from
the scheduled task.) Use the registered entry point, which runs with the user
environment:

    schtasks /run /tn "CIS_Pipeline_Watchdog"

Its log is `_logs/watchdog.log`; its verdict is `_logs/pipeline_state.json`.

To reach the pod from a session that lacks the variables, read them from
`HKCU\Environment` into the child's environment first (that is what
`_tools/_pod.py` does) -- never let `rsc.py` fall back to a compiled-in default,
because that default names a decommissioned pod.

## Two things about `code/` and `plan/`

* `code/` is the **as-run generation** -- the sources that produced the numbers
  in `results/`. It is not a mirror of any live work tree, and it is expected to
  differ from one in places. For the E5p chain in particular, the live work tree
  has moved on since these artefacts were produced.
* `plan/` is the **frozen v5 baseline** this package was built against. Later
  plan revisions live outside the package.

**Corrected 2026-09-25, because the paragraph above described the re-cut packages
and not a build of this tree.** The canonical packager copies the working tree, so
what actually ships is:

* `code/` is the **working tree at build time** -- every stage script and tool as
  the tree held it. It is not a frozen "as-run generation". rc2/rc3/rc4 inherited
  their `code/` from the frozen build and patched six named files into it, which
  is why one of them shipped a `run_pipeline.py` two generations behind the live
  one: the sentence above made that look intended. A build of the tree does not
  have that failure mode, and the currency of a script is now a property of the
  tree rather than of this note.
* `plan/` holds the **governing plan, v10**, as the `.md` the plan is authored in
  (author's ruling 3); v5-v9 are void by v10's own footer. Earlier packages
  carried the v5 `.docx`, which nothing in this tree can write -- only read -- so
  a superseded plan was shipping in a format the tree cannot regenerate.

## Line endings

`.cmd` files must be **CRLF and ASCII-only**: cmd.exe mis-parses LF-only files
(fragments get executed as commands), and non-ASCII comments render as mojibake
under the OEM code page.

## Corrected 2026-10-17: the `code/` and `plan/` paragraphs above describe a package, not this repository

The two paragraphs above ("Two things about `code/` and `plan/`") were written
about the **delivery package**, which carried the pipeline under `code/` and the
governing plan under `plan/`. Neither directory exists in this repository. Here:

* the pipeline is `_server/` (one script per stage) and `_tools/` (the harness);
* the plan is at the root, as `数据黑产韧性研究-冲刺计划书v10.md`.

The paragraphs are kept, because the failure mode they record is real and
transferable -- a package shipping a superseded plan in a format the tree cannot
regenerate, and a `code/` inherited from a frozen build instead of from the tree
-- but the paths they name are not paths here. A reader who follows them into
this repository finds nothing, and that is a defect in this file rather than
evidence that a directory was removed.
