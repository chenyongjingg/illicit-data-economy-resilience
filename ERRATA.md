# ERRATA -- the delivery face

Built 2026-09-24 by the C-247 re-cut, from the frozen package
`cis_sprint_20260924` (left byte-intact). This tree **supersedes
`cis_sprint_20260924_rc2`** and, for delivery purposes, the frozen tree.

**2026-09-25 -- this document is now part of the tree**, not of a re-cut: it lives
at `ERRATA.md` in the working tree and ships from there with every package built
after it. The header above is kept as the state it recorded. It is worth noticing
what it recorded: it names `rc3` while rc4 was shipping it, and rc4 shipped it
unchanged -- a delivery document that did not name the tree it was in. That is the
same class as the defects below, and it is why the title line above was changed.

## 1. Why rc3 exists on top of rc2: rc2 still carried a pod endpoint

rc2 was built by copying the frozen tree and substituting six *named* files.
That repairs what a ledger entry happens to name. It does not repair what
exists *by type*. The copy brought along

    code/_tools/.rsc_cache.json      99 bytes

a runtime cache written into `_tools/` by `rsc.py`, holding three keys:

    host   pod hostname      (37 chars -- the DECOMMISSIONED pod)
    ip     its resolved address
    at     unix time of the write (2026-09-23)

Both the frozen package and rc2 pin that file in their own `_MANIFEST.sha256`,
so it could not be edited in place either. Eleven copies exist under the working
tree: ten byte-identical (decommissioned host, written 2026-09-23), one -- the
live work-tree copy -- naming the CURRENT pod (written 2026-09-24).

WHICH COPY LANDS DEPENDS ON THE BUILDER, and the two differ:

  * the canonical packager `_tools/make_output_package.py` copies the LIVE
    `_tools/`, so it would ship the *current* endpoint;
  * rc2's recipe (and this one) copies the FROZEN package, so it re-ships the
    *decommissioned* one.

Either way the exclusion is the fix. What is wrong is **sanitising the file's
contents**: it is an unintended runtime cache, and rewriting it to name the
right host would make it look like a deliberate part of the package.

## 1a. Measured carrier census (files containing each string)

| needle | frozen | rc2 | rc3 |
|---|---|---|---|
| decommissioned host | 7 | 8 | 6 |
| current host | 0 | 2 | 2 |
| resolved ip | 1 | 2 | 1 |
| **`CIS_PASS` literal** | **1** | **0** | **0** |
| dotfiles | 1 | 1 | 0 |
| **retired port default `25355` in `code/`** | **1** | **1** | **1** | **0** |

The password was the actual credential: it was compiled into the packaged
`rsc.py` and is now absent (rc2 fixed that; rc3 keeps it fixed). The remaining
host strings are all **functional or historical**, and each was read to confirm
it: `watchdog.cmd` must `set CIS_HOST`; the ledger must record which host
answered on which day; `_build_repo_stage.py` asserts on the OLD host so a pod
change fails loudly; `_probe_dns.py` resolves it; `58_E9_provenance.py` and
`results/51_E9_series.json` carry a `produced_on` provenance field. "A scan
matched a host string" is not "a credential leaked" -- the discriminator is
which file, and why.

## 1b. The other half of the endpoint: the port kept a retired default

Section 1 is about a cache that named the host. The host is only half of an
endpoint, and the other half was still there:

    PORT = int(os.environ.get("CIS_PORT", "25355"))      # 25355 = the
                                                         # decommissioned pod

Measured, the same line byte-for-byte in all four copies: the live tool tree,
the repo stage, the frozen package and rc3. Corroborated by the watchdog log,
which shows `25355` seven times (the decommissioned pod) and `28153` three
times (the current one).

This is a side effect of the credential repair itself. Removing the HOST
default made HOST required while leaving PORT a default, so a run that sets
`CIS_HOST` and not `CIS_PORT` reaches for a port that belonged to a
decommissioned host -- the same silent-no-op family as C-242, where changing
one carrier had no effect and nothing said so.

Repair:

  * `_tools/_build_repo_stage.py:sanitize_rsc()` -- PORT now required, no
    default, matching HOST and PASS; plus a receipt asserting that **no**
    endpoint keeps a default afterwards. This is the fix for the next stage
    build. The stage itself was not rebuilt here: publishing is the author's
    step.
  * this re-cut applies the same rewrite to the package's own `rsc.py`.
  * `CIS_USER` deliberately KEEPS its default (`root`). An account is not an
    endpoint: it points at nobody's host and is not a credential, and every
    sanctioned entry point sets it anyway. Removing defaults is for values that
    point somewhere.

Census (files containing the string), with the port as its own needle:

| needle | frozen | rc2 | rc3 | rc4 |
|---|---|---|---|---|
| decommissioned port `25355` | 1 | 1 | 1 | 0 in `code/` |

## 2. The repair is a class rule, and it is applied in three places

`.rsc_cache.json` reached every package because it is a **dotfile**, and the
packager's exclusion tables (`SKIP_DIRS`, `SKIP_EXT`, `SKIP_FILES`,
`SKIP_PREFIXES`) had no dotfile rule at all. Editing the file, or deleting this
one copy, would fix the instance and leave the class.

  * `_tools/make_output_package.py` -- `.rsc_cache.json` added to
    `SKIP_FILES`; the reason added to its `Excluded` table; **hidden
    directories** excluded by the same rule; and a new
    `assert_no_dotfiles()` step re-reads the finished package off disk and
    FAILS THE BUILD if any dotfile or hidden directory is in it. This is the
    fix for every future build.
  * this re-cut applies the *same* rule (same four tables) rather than a
    one-off `rm`, so the two cannot drift apart.
  * the alternative -- sanitising the file's contents -- is rejected above.

Nothing was hand-deleted from any shipped tree. rc3 is a regeneration.

## 3. The six substitutions (carried over from rc2)

| # | path | why |
|---|---|---|
| 1 | `FINAL_SUMMARY.md` | plan-vs-ledger conflict (C-244): v9's K1 wrote an assertive "~0.214 of leak" that the ledger's C-234 (3) forbids. Carries the live version, which appends a C-244 erratum section. |
| 2 | `pipeline_reports/16_E5p_temporal_gnn.md` | same, plus the packaged copy was missing the C-205 dual-scope disclosure (it diverged from the live tree by one line). |
| 3 | `pipeline_reports/progress.md` | the packaged copy was the ledger as of the original build; replaced with the live ledger. |
| 4 | `code/_tools/rsc.py` | **credential carrier.** The packaged copy was byte-identical to the pre-sanitisation work-tree file and held a `CIS_HOST` default (37 chars) AND a `CIS_PASS` default. Replaced with the sanitised revision (`os.environ["CIS_HOST"]` / `os.environ["CIS_PASS"]`, no defaults for either). |
| 5 | `code/_tools/watchdog.cmd` | packaged copy was **LF-only** (cmd.exe mis-parses LF: fragments execute as commands) and pre-dated the FIX (a)/(b)/(c) revision -- it also retargeted the decommissioned pod and could never report a non-zero exit to Task Scheduler. |
| 6 | `code/_tools/register_watchdog.cmd` | same LF-only defect. |

New files: this `ERRATA.md`, and `OPERATIONS.md` (the credential *mechanism*,
never a value).

## 4. Deliberately NOT changed

* `code/_server/53_E5p_temporal_gnn_rc6.py` and `code/_tools/_c19*.py` /
  `_c20*.py` still contain the retired phrase in comments and docstrings. They
  are historical records of what those runs said; rewriting them would destroy
  the evidence that the wording was ever asserted. Superseded, not edited --
  same principle as the ledger's rule for `_superseded_*` copies.
* Any measured number, any artefact under `results/`, any figure.
* The frozen tree itself.

## 5. Open (author)

1. **Which tree is the delivery object.** rc3 strictly dominates rc2 (rc2
   carries a pod endpoint and should not be delivered). The remaining question
   is whether to *replace* the frozen `cis_sprint_20260924` or keep both.
   **Status 2026-09-25**: the re-cut chain ends here. A single canonical build,
   `cis_sprint_20260925`, is the delivery object; rc2/rc3/rc4 stay on disk as
   superseded candidates. Whether to *replace* the frozen `cis_sprint_20260924`
   remains the author's call, as it was.
2. `CIS_PASS` is **not** in this package and must not be; the mechanism is in
   `OPERATIONS.md`.
3. The decommissioned pod answered SSH on 2026-09-24 between 08:13 and 16:54
   (19 watchdog ticks, all `pod: reachable`) -- so "not the current password"
   does not make a credential in the older packages expired. Deleting the pod
   is what retires it.
4. `plan/` in this package is the **frozen v5 baseline**. The current governing
   plan is v9 (2026-09-24 23:42), which is **not packaged**: its K1 carries the
   wording that C-234 (3) forbids, so shipping it as-is would ship a
   contradiction with this file. v9 itself awaits an author erratum.

   **Closed 2026-09-25** (author's rulings 1-3, ledger C-372): `plan/` now carries
   **v10**, whose footer voids v5-v9, and v10's K1 was brought into the wording
   C-234 (3) requires. The item above is kept as what was true when it was
   written. The `.docx` form is not shipped by ruling 3.
6. **Whether to rebuild the repo stage.** `sanitize_rsc()` now also makes PORT
   required, but the built stage still carries the old PORT default; the fix
   lands on the next rebuild. Rebuilding publishes, which is the author's call.


## 6. Stopping rule (this re-cut)

This is the **last** re-cut of the W1 package face. Every later finding
goes to the ledger and to the author-item list, not to another tree:
a delivery object that changes on every discovery is one nobody can
name. The candidate named here supersedes rc2 and rc3.

**2026-09-25 -- the rule held, and the one build since then is not a re-cut.** The
author's ruling 3 required the package to carry the live plan, so one more build
was mandated. It was made as the **canonical** build (`cis_sprint_20260925`, by
`_tools/make_output_package.py`), not as an `rc5` cut of a frozen tree: one
object, named by its build date, reproducible from the working tree. Everything
found afterwards still goes to the ledger and the author-item list -- which is
why the two documents that existed only inside the re-cut packages were moved
into the tree instead of being patched into another tree.

## 7. What the canonical build measured (2026-09-25)

Censuses below are over the package `cis_sprint_20260925` (1269 files before the
manifest, 283 of them under `results/`), measured by re-walking the built tree:

| needle | frozen | rc2 | rc3 | rc4 | this build |
|---|---|---|---|---|---|
| dotfiles / hidden dirs | 1 | 1 | 0 | 0 | 0 |
| `CIS_PASS` literal, any file | 1 | 0 | 0 | 0 | **0** (build refuses otherwise) |
| endpoint defaults in `code/_tools/rsc.py` | 3 | 1 | 1 | 0 | **0** |
| `USER` default kept by design | 1 | 1 | 1 | 1 | **1** |
| retired port default `25355` in `code/` | 1 | 1 | 1 | 0 | **0** |

"Endpoint defaults" is counted by AST over the module-level bindings `HOST`,
`PORT`, `PASS`: a binding counts when its value still contains an
`os.environ.get(...)` call, i.e. when it can fall back. `USER` is counted
separately because it is not an endpoint and not a credential -- `root` names
nobody's host -- and `sanitize_rsc()` says so in the same words.

Two rules changed from "checked after the fact" to "the build fails":

* the transport rewrite is applied by the packager and its receipt is re-read
  off disk, so a future edit that re-introduces a default cannot ship quietly;
* the live credential is refused **anywhere** in the package, by name of the
  offending file. Host and port strings are not treated the same way: they occur
  legitimately in notes, probes and provenance fields, and the discriminator is
  which file and why -- the distinction section 1a makes.

This file and `OPERATIONS.md` were moved into the working tree on the same day.
They had existed only inside the re-cut packages, so no build of the tree could
reproduce them: the delivery face was not a function of the tree, which is the
defect class this section closes.
