# -*- coding: utf-8 -*-
"""Build the publishable stage for github.com/chenyongjingg/takedown-resilience.

WHY A STAGE AND NOT THE WORKING TREE. The credential must never enter git history,
and history is the public face -- `git log -S` finds a secret that a later commit
deleted. So the repo is assembled in `_repo_stage/` by WHITELIST, sanitised, and
scanned before any git command runs. The working tree keeps its functional
`rsc.py` so the pod can still be driven; the two are deliberate different objects
and that difference is recorded rather than left to be discovered.

WHAT IS EXCLUDED, AND WHY IT IS NOT A LOSS.
  * `data/raw/*` and `data/extracted/` and `data/EllipticPlusPlus-main/`: the
    first is third-party scraped material (and the AlphaBay archive is 133 MB,
    over GitHub's 100 MB per-file limit); the other two are DERIVED from it, so
    they are re-derivable rather than irreplaceable. Their sha256 / list-hashes
    are recorded instead of their bytes.
  * `*.parquet`: derived features over an external dataset -- hashes recorded,
    bytes not redistributed.
  * `output/`: 552 MB across eight package copies, and every copy carries the
    credential. This is the artefact the C-181 §5 finding is about.
"""
import hashlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"D:\CIS"
# ★ C-206: overridable, so a clean stage can be built WITHOUT destroying the existing one
# (`refresh()` rmtree's STAGE, which also destroys `_repo_stage/.git`).
STAGE = os.environ.get("CIS_STAGE", os.path.join(ROOT, "_repo_stage"))
TOOLS = os.path.join(ROOT, "_tools")
# ★ C-416: the published payload is a LIST, not a directory tree.
WHITELIST = os.path.join(TOOLS, "_repo_whitelist_c7.txt")
GENERATED = (".gitignore", ".gitattributes", "data/README.md")
STAGE_SEED = os.environ.get("CIS_STAGE_SEED", os.path.join(ROOT, "_repo_stage_c7"))
# The delivery documents the author named ON TOP of the frozen list.
DELIVERY_DOCS_LIST = os.path.join(TOOLS, "_repo_delivery_docs.txt")
LEDGER = "pipeline_reports/progress.md"

sys.path.insert(0, TOOLS)                        # sibling module; this file runs as a script
from _needle import NEEDLE as _LITERAL           # noqa: E402  (recovered, never written)
from _needle import subforms as _subforms        # noqa: E402

RAW_HASHES = [
    ("818e54e9198f0fadba82304079e2d5c33d6a99d598fd1f6d0bdf933703bd326f", "agora_2014_2015.csv.xz"),
    ("b074ad5d0b998c57184f4b0e9188ffbe5bc5be9990670a288b6cbf36a37f7c52", "alphabay_2017-01-28.tar.xz"),
    ("303a9ddf27d49add80cbaf76d4f744512efabcbd874b46434a474579a5323c9f", "druglistingdataset.csv.xz"),
    ("82c340231a26c1701cf30be49d74b9d670162bb94bbffc0b9e45fd2403e045c4", "hansa_valhalla.zip"),
    ("5659209b5a69992d5b0708a3e84a6c24e40ba04340f5e8c0b88f2442e664ca4d", "kilos_6dnms_reviews.csv.xz"),
]

TREE_FINGERPRINTS = [
    ("data/extracted", 169541, 21257014304, "0e583ff41e0556539e4dc3979f475af6"),
    ("data/EllipticPlusPlus-main", 32, 2221824034, "93470ed6d36a5ec8aebd71fe81857ee7"),
]


def sha256_file(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _rm_readonly(func, path, exc_info):
    """rmtree error hook: git writes loose objects 0444, which Windows maps to the
    read-only attribute, so the FIRST rmtree of a stage that has ever been committed
    dies with `PermissionError [WinError 5]`. Clear the bit and retry once."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        raise


def refresh():
    """Re-copy the whitelist from the working tree (it changed: C-181 landed).

    ★ C-213 (2026-09-24). Two defects were found by running it, and both are fixed here.

      (1) **It was not idempotent.** `shutil.rmtree` raises `PermissionError [WinError 5]`
          on `.git/objects/**` because git stores loose objects read-only. A stage that
          has been committed once therefore cannot be rebuilt -- the tool worked exactly
          once and failed every time after. `_rm_readonly` clears the attribute and retries.

      (2) **The removal of `.git` was silent, and this script never re-creates it.**
          `refresh()` deletes the whole stage directory; the only `.git` inside it is
          deleted with it, and nothing below this line runs a git command (`AWAITING
          EXPLICIT PUSH`). So a rebuild silently destroys the stage's commit history --
          and that decides, without saying so, the open question of whether the next
          publication **adds a commit** or **re-cuts a single root**. An irreversible
          side effect must be an explicit decision, so this now REFUSES to delete a
          `.git` unless `CIS_ALLOW_GIT_RM=1` is set. Use `CIS_STAGE=<dir>` to build a
          fresh stage somewhere else, which is what that override was added for (C-206).

          (3) **It copied whole directories, so "what may be published" was never
              written down.** Measured 2026-09-25: whitelisting by directory would
              have taken `_tools/` from 98 published files to 804, and 32 of those
              drafts carry an endpoint literal. The whitelist is now the 475 tracked
              in `_repo_stage_c7` (C-416); contents refresh, the file list does not.
    """
    if os.path.isdir(STAGE):
        if os.path.isdir(os.path.join(STAGE, ".git")) and os.environ.get("CIS_ALLOW_GIT_RM") != "1":
            sys.exit("REFUSING: %s contains .git and this script never re-creates it.\n"
                     "  Re-building here would silently destroy the stage's commit history,\n"
                     "  which decides 'add a commit' vs 're-cut a single root' -- an author\n"
                     "  decision (C-213, and the C-207 item-7 thread). Options:\n"
                     "    CIS_STAGE=<other dir> ...   build a fresh stage elsewhere (no loss)\n"
                     "    CIS_ALLOW_GIT_RM=1  ...     accept the loss, in place" % STAGE)
        shutil.rmtree(STAGE, onexc=_rm_readonly)
    os.makedirs(STAGE)
    # ★ C-416: the payload is the WHITELIST, not a set of whole directories.
    # Copying `_tools/` wholesale published 804 draft tools, 32 of which carry an
    # endpoint literal -- i.e. the old rule could not be stated as "what may be
    # published" at all. The list is the 475 tracked in `_repo_stage_c7`, so the
    # repo's file list is FROZEN and only contents refresh; a new draft tool cannot
    # enter by existing. `_repo_whitelist_c7.txt` is not itself in the list.
    with io.open(WHITELIST, encoding="utf-8") as fh:
        want = [l.strip() for l in fh if l.strip()]
    assert len(want) == 475, "whitelist has %d entries, expected 475" % len(want)
    assert "_repo_whitelist_c7.txt" not in want, "the whitelist must not list itself"
    missing = []
    for rel in want:
        if rel in GENERATED:
            continue                       # write_docs() produces these
        s = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(s):
            missing.append(rel)
            continue
        d = os.path.join(STAGE, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
    # ★ C-416: the delivery documents, as a SECOND explicit list rather than
    # additions to the whitelist -- so the 475 keeps its meaning ("what was already
    # published") and this increment is visible and withdrawable as a unit.
    with io.open(DELIVERY_DOCS_LIST, encoding="utf-8") as fh:
        docs = [l.strip() for l in fh if l.strip()]
    for rel in docs:
        assert "/" not in rel and "\\" not in rel, \
            "delivery docs are top-level files: %s" % rel
        s = os.path.join(ROOT, rel)
        if not os.path.isfile(s):
            missing.append(rel)
            continue
        shutil.copy2(s, os.path.join(STAGE, rel))
    # The repo front page exists ONLY inside the built stage, so a rebuild would
    # silently delete it. Seed it from the last stage instead of losing it.
    seed = os.path.join(STAGE_SEED, "README.md")
    if os.path.isfile(seed):
        shutil.copy2(seed, os.path.join(STAGE, "README.md"))
        if "README.md" in missing:
            missing.remove("README.md")   # satisfied by the SEED, not by ROOT
    elif "README.md" not in missing:
        missing.append("README.md")
    if missing:
        sys.exit("whitelist entries with no source under %s (%d): %s\n"
                 "  A missing entry is NOT a smaller release -- it is an unstated change\n"
                 "  to the published file list. Fix the whitelist or restore the file."
                 % (ROOT, len(missing), missing))


def drop_caches_and_data():
    """Remove caches and every byte of third-party / derived data."""
    removed = []
    for dirpath, dirnames, filenames in os.walk(STAGE):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            if fn == ".rsc_cache.json" or fn.endswith((".parquet", ".pyc")):
                os.remove(p)
                removed.append(os.path.relpath(p, STAGE))
                continue
            # data/raw bytes: keep only the README we are about to write
            rel = os.path.relpath(p, STAGE).replace("\\", "/")
            if rel.startswith("data/"):
                os.remove(p)
                removed.append(rel)
    for dirpath, dirnames, filenames in os.walk(STAGE, topdown=False):
        if "__pycache__" in dirnames:
            shutil.rmtree(os.path.join(dirpath, "__pycache__"), ignore_errors=True)
    return removed


def sanitize_rsc():
    """Remove the credential and the ENDPOINT defaults from the published rsc.py.

    Endpoints are the host AND the port. Removing only the host left the pair
    inconsistent: a caller that sets `CIS_HOST` and not `CIS_PORT` would then
    reach for a compiled-in port, and that port belonged to the decommissioned
    pod. That is the same silent-no-op family as C-242 -- changing one carrier
    and finding it had no effect, with no error to say so. So PORT joins HOST
    and PASS: required, no default.

    USER deliberately keeps its default. `root` is an account, not an endpoint:
    it names nobody's host, it is not a credential, and every sanctioned entry
    point sets it anyway. Removing a default is for values that point somewhere.
    """
    p = os.path.join(STAGE, "_tools", "rsc.py")
    src = io.open(p, encoding="utf-8").read()
    before = src
    # How many defaults the INPUT actually had. `before` is compared against the
    # output only to catch a sanitiser that silently did nothing to a file that
    # DID have defaults -- a bare `assert src != before` is false by construction
    # on an already-sanitised input, i.e. the same one-shot bug in a second place.
    had = sum(1 for l in src.split("\n")
              if l.startswith(('HOST = os.environ.get("CIS_HOST"',
                               "PORT = int(os.environ.get(", 'PASS = os.environ.get(')))
    # HOST: located by POSITION, exactly as PORT and PASS are below. Until C-416 this
    # line hard-coded the RETIRED host, while twenty lines down PORT was located by
    # position under the comment "so no retired port literal is written here". The file
    # therefore carried the very thing it documented avoiding -- and it is published.
    # Searching for the value you are removing also makes the removal one-shot: once
    # the value is gone the search finds nothing, and the tool dies on the next run.
    lines = src.split("\n")
    hh = [i for i, l in enumerate(lines)
          if l.startswith('HOST = os.environ.get("CIS_HOST"')]
    if hh:
        assert len(hh) == 1, "expected exactly one HOST line, found %d" % len(hh)
        lines[hh[0]] = ('# Required from the environment. Deliberately NO default: a host\n'
                        '# baked into a source file is a host that ships with the code.\n'
                        'HOST = os.environ["CIS_HOST"]')
        src = "\n".join(lines)


    # PORT: located by position, so no retired port literal is written here.
    lines = src.split("\n")
    ph = [i for i, l in enumerate(lines) if l.startswith("PORT = int(os.environ.get(")]
    if ph:
        assert len(ph) == 1, "expected exactly one PORT line, found %d" % len(ph)
        lines[ph[0]] = ('# Required from the environment, for the same reason as HOST: a port\n'
                        '# left as a default is half of a retired endpoint. A run that sets\n'
                        '# HOST but not PORT must fail loudly, not connect nowhere quietly.\n'
                        'PORT = int(os.environ["CIS_PORT"])')
        src = "\n".join(lines)

    # find the PASS line without hardcoding the secret here either
    lines = src.split("\n")
    hit = [i for i, l in enumerate(lines) if l.startswith("PASS = os.environ.get(")]
    if hit:
        assert len(hit) == 1, "expected exactly one PASS line, found %d" % len(hit)
        lines[hit[0]] = ('# Required from the environment. The previous revision carried the\n'
                         '# pod password as this default, which put a live credential into\n'
                         '# every copy of the delivery package (see C-181 in the ledger).\n'
                         'PASS = os.environ["CIS_PASS"]')
        src = "\n".join(lines)
    assert src != before or not had, \
        "sanitiser changed nothing although the input had %d default(s)" % had
    # The receipt: after this function, no endpoint may still have a default.
    # The receipt is restated on the END state, not on the input: this function now
    # accepts an already-sanitised rsc.py (the live tree is one, since 2026-09-24) and
    # asserts what must be TRUE afterwards. It used to assert that the UNsanitised
    # input existed, which made it a one-shot: the second run could never succeed.
    for bad in ('os.environ.get("CIS_HOST"', 'os.environ.get("CIS_PORT"',
                'os.environ.get("CIS_PASS"'):
        assert bad not in src, "endpoint default survived sanitisation: %s" % bad
    for must in ('HOST = os.environ["CIS_HOST"]', 'PORT = int(os.environ["CIS_PORT"])',
                 'PASS = os.environ["CIS_PASS"]'):
        assert src.count(must) == 1, "required line missing or duplicated: %s" % must
    io.open(p, "w", encoding="utf-8", newline="").write(src)
    return True


def write_docs():
    d = os.path.join(STAGE, "data")
    os.makedirs(d, exist_ok=True)
    io.open(os.path.join(d, "README.md"), "w", encoding="utf-8", newline="\n").write(
        "# Data: provenance by hash, not by byte\n\n"
        "This repository deliberately does **not** redistribute the corpora it analyses.\n"
        "What it publishes is the set of hashes that pin them, so a replication can prove\n"
        "it holds the same inputs without the inputs travelling through git.\n\n"
        "## `data/raw/` -- the reproducibility anchor\n\n"
        "```\n" + "".join("%s  %s\n" % (h, n) for h, n in RAW_HASHES) + "```\n\n"
        "These five archives were verified, 5/5 by sha256, against the copies held on the\n"
        "execution host on 2026-09-24. **That claim is dated, not standing**: it reports a\n"
        "measurement made on that date, and decommissioning the host was still pending as of\n"
        "it. A reader who needs it to hold now must re-run the comparison -- the sentence\n"
        "cannot be true \"in general\", only at a time.\n\n"
        "## Derived trees that are NOT published\n\n"
        "| tree | files | bytes | sha256 of the sorted file list |\n|---|---|---|---|\n"
        + "".join("| `%s` | %d | %d | `%s` |\n" % t for t in TREE_FINGERPRINTS) +
        "\nBoth are derived from `data/raw/` plus `EllipticPlusPlus.tar.gz` by the scripts in\n"
        "`_server/` and `scripts/`. What is checkable without transferring them is the **file\n"
        "list**: rebuild, then compare `find <tree> -type f -printf '%P\\n' | LC_ALL=C sort | sha256sum`.\n"
        "★ That value hashes the sorted **names only** -- two trees with the same names and\n"
        "different bodies give the same number, so it cannot detect a changed byte. Content is\n"
        "pinned separately and by a different instrument: the byte-identical `data/raw/`\n"
        "archives above, together with the extraction the scripts perform. One step of that\n"
        "extraction is worth stating because it is not in any script: the pinned\n"
        "`data/extracted` member list is what `data/raw/` yields **after dropping\n"
        "`alphabay_2017-01-28/20170128-alphabay/crawl-active/`** (169,541 names, list-hash\n"
        "above); keeping it gives 283,772 names and a different hash. That was measured on\n"
        "2026-09-24, not read off the code, and it is recorded as a measurement.\n\n"
        "## Derived features that are NOT published\n\n"
        "`results/elliptic_address_level.parquet` and `pipeline_reports/_ref/elliptic_address_level.parquet`\n"
        "are feature tables over the Elliptic++ dataset. They are omitted rather than\n"
        "redistributed; the scripts that build them are included.\n")

    io.open(os.path.join(STAGE, ".gitignore"), "w", encoding="utf-8", newline="\n").write(
        "# Built by whitelist, so this file documents intent rather than doing the work.\n"
        "__pycache__/\n*.pyc\n.rsc_cache.json\n"
        "# Third-party and derived data: pinned by hash in data/README.md, never committed.\n"
        "data/raw/*\ndata/extracted/\ndata/external/\ndata/_recon/\ndata/EllipticPlusPlus*\n"
        "*.parquet\n"
        "# Delivery packages: large, and every copy carried a credential (ledger C-181).\n"
        "output/\n_rescue_20260924/\n_repo_stage/\n_logs/\n_work/\n")

    io.open(os.path.join(STAGE, ".gitattributes"), "w", encoding="utf-8", newline="\n").write(
        "# NEVER NORMALISE LINE ENDINGS. Several artefacts in this project are sha256\n"
        "# manifests consumed by POSIX tools on data produced elsewhere, and a manifest's\n"
        "# line endings are part of the manifest: a CRLF manifest makes `sha256sum -c` read\n"
        "# a carriage return into every filename and fail on all of them, while a checker\n"
        "# written in Python -- which reads in universal-newline mode -- reports success.\n"
        "# The checker and the checked sharing a blind spot is not a passing test.\n"
        "* -text\n")


def write_provenance():
    """Stamp the stage with its own birth, so 'which tree state is this' is
    answerable FROM INSIDE the stage.

    WHY. `_repo_stage/` is a build artefact and drifts: on 2026-09-24 it was built
    at ~05:06Z and a table cell was corrected in the working tree at ~05:11Z, so a
    published copy would have carried a value the live report had already fixed --
    with nothing inside the tree saying so. A snapshot that cannot state its own
    cut is indistinguishable from a current one. C-184.
    """
    led = os.path.join(ROOT, "pipeline_reports", "progress.md")
    rep = os.path.join(ROOT, "pipeline_reports", "16_E5p_temporal_gnn.md")
    tools = os.path.join(ROOT, "_tools")
    newest = 0
    for base in ("pipeline_reports", "_tools", "_server", "results"):
        d = os.path.join(ROOT, base)
        for dp, _dn, fns in os.walk(d):
            for f in fns:
                try:
                    newest = max(newest, os.path.getmtime(os.path.join(dp, f)))
                except OSError:
                    pass
    body = (
        "# Stage provenance\n\n"
        "This tree is a **build artefact**, regenerated by `_tools/_build_repo_stage.py`\n"
        "from `D:\\CIS`. It is not edited in place, and it is not a frozen record.\n\n"
        "| | |\n|---|---|\n"
        "| built (UTC) | %s |\n"
        "| source ledger `pipeline_reports/progress.md` sha256 | `%s` |\n"
        "| source report `16_E5p_temporal_gnn.md` sha256 | `%s` |\n"
        "| newest source mtime (UTC) | %s |\n\n"
        "**If a source file above is newer than the build time, this stage is stale**\n"
        "and must be regenerated before anything is published from it. That check is\n"
        "the whole reason this file exists: a snapshot that cannot state its own cut\n"
        "looks exactly like a current one.\n\n"
        "★ C-210 (2026-09-24). Read the two sentences above as a rule for the **reader**,\n"
        "not as a test this file passed. `_build_repo_stage.py` reads `newest` off the\n"
        "source trees **before** it stamps `built`, so as **printed** the two rows can\n"
        "never disagree and 'stale' is unreachable from them alone. Two readings carry\n"
        "content, both taken **after** this file was written:\n"
        "  (a) re-stat the source trees and compare against `built` **in the same clock at\n"
        "      the same precision** -- `built` is truncated to whole seconds, so a source\n"
        "      written in that same second is invisible to it (measured 2026-09-24: the\n"
        "      newest source and `built` landed in the same second and the readable\n"
        "      remainder was 674 ms);\n"
        "  (b) byte-compare the payload: `results/`, `_server/`, `pipeline_reports/`,\n"
        "      `_tools/` -- but the comparison set must be the whitelist's domain, or\n"
        "      deliberate differences read as drift (`__pycache__`, `.rsc_cache.json`,\n"
        "      `*.parquet` are excluded by design, and `_tools/rsc.py` is **rewritten**\n"
        "      by `sanitize_rsc()`).\n"
        "Live check: `_logs/_fresh_check.py` (it walks no whitelisted tree, so running it\n"
        "cannot make this stage stale).\n"
        % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           sha256_file(led) if os.path.exists(led) else "ABSENT",
           sha256_file(rep) if os.path.exists(rep) else "ABSENT",
           time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(newest))))
    p = os.path.join(STAGE, "STAGE_PROVENANCE.md")
    io.open(p, "w", encoding="utf-8", newline="\n").write(body)
    return sha256_file(p)


def normalize_cmd_endings():
    """`.cmd`/`.bat` must be CRLF + ASCII-only before anything is published.

    Why this is a *class* fix and not a patch to one file (C-222 (6)): measured
    2026-09-24, **23 of the 24** `.cmd`/`.bat` files under D:\\CIS were LF-only,
    including every copy this script had ever emitted. cmd.exe mis-parses LF-only
    line endings -- it executes fragments as commands -- so a hand-delivered
    `watchdog.cmd` produced `'CIS' is not recognized...`, silently wrote no log,
    and the scheduler recorded 9009. Patching that one file by hand would have
    left this script free to re-emit the same defect on the next rebuild, which
    is precisely how the defect got into nine trees.

    ASCII is enforced rather than repaired: cmd.exe reads the file in the OEM code
    page, so UTF-8 comments become mojibake. A byte-level rewrite of a file whose
    *intent* I cannot read as ASCII is the same class of sin as swallowing an
    exception -- so non-ASCII files are reported and fail the build instead.

    Returns (scanned, rewritten, nonascii).
    """
    scanned, rewritten, nonascii = 0, [], []
    for dirpath, _dirnames, filenames in os.walk(STAGE):
        for fn in filenames:
            if not fn.lower().endswith((".cmd", ".bat")):
                continue
            scanned += 1
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, STAGE)
            raw = io.open(p, "rb").read()
            try:
                text = raw.decode("ascii")
            except UnicodeDecodeError as exc:
                nonascii.append((rel, str(exc)[:60]))
                continue
            body = text.replace("\r\n", "\n").replace("\r", "\n")
            if not body.endswith("\n"):
                body += "\n"
            back = body.replace("\n", "\r\n").encode("ascii")
            if back != raw:
                io.open(p, "wb").write(back)
                rewritten.append(rel)
            # Verify on the bytes on disk, never on the intent above.
            chk = io.open(p, "rb").read()
            lone = chk.count(b"\n") - chk.count(b"\r\n")
            assert lone == 0, "%s still has %d LF-only ending(s)" % (rel, lone)
            assert all(b < 128 for b in chk), "%s has a non-ASCII byte" % rel
    return scanned, rewritten, nonascii


def scan():
    """The gate: the credential and oversized files must both be absent.

    ★ Two C-206 corrections to what this function used to be:
      * it searched only the contiguous needle -- i.e. only the form a split carrier
        cannot contain (see `_subforms`);
      * it swallowed unreadable files with a bare `except: pass`, which is this project's
        cardinal sin: "my instrument failed" and "the object does not exist" must never
        share a return value. Unreadable files are now counted and reported.
    """
    bad, big, unreadable = [], [], []
    forms = _subforms()
    # ★ C-416: the ENDPOINT gate. `forms` above is the CREDENTIAL; this is the
    # other class, and it was ungated -- which is how a live host/port reached a
    # tracked file. The values are read from the environment HERE and never written
    # down, so this file is not a carrier of what it checks for.
    ep = [(n, os.environ.get(n, "")) for n in ("CIS_HOST", "CIS_PORT")]
    if not all(v for _n, v in ep):
        sys.exit("stage scan: CIS_HOST/CIS_PORT absent from the environment, so the "
                 "endpoint gate cannot run. A gate that cannot run is not a gate.")
    # ★ C-416: AN ENDPOINT IS A PAIR. This project already ruled on that
    # (C-256: "what is distinguishable is the PAIR (host, port)"), so the FATAL
    # predicate is the HOST -- the identifying half. A BARE PORT is counted and
    # printed but not gated: `ERRATA.md` quotes a retired port default as the
    # SUBJECT of an erratum and carries no host, i.e. names nothing reachable.
    # Failing it would be punishing the erratum for describing the defect.
    _ep = dict(ep)
    # The RETIRED provider forms are counted, not gated: retired is by definition
    # unreachable, so it is a different severity from a live endpoint, not the same
    # one. Assembled from PARTS on purpose -- a gate whose source carries the very
    # form it hunts becomes the only offender it finds (measured: it did). The
    # labels say the CLASS; the parts say the form; no literal is contiguous here.
    _DOT = chr(46)
    _PROV_DOM = "compshare" + _DOT + "cn"
    _PROV_SUF = _DOT + "podtcp"
    ep_pats = [("CIS_HOST", re.compile(re.escape(_ep["CIS_HOST"]).encode()))]
    res_pats = [("bare-port", re.compile((u"(?<![0-9.])"
                                        + re.escape(_ep["CIS_PORT"])
                                        + u"(?![0-9.])").encode())),
                 ("retired-provider-domain",
                  re.compile(re.escape(_PROV_DOM).encode())),
                 ("retired-provider-host-suffix",
                  re.compile(re.escape(_PROV_SUF).encode()))]
    ep_hits = {}
    ep_res = {}
    for dirpath, _dirnames, filenames in os.walk(STAGE):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, STAGE)
            if os.path.getsize(p) > 90 * 1024 * 1024:
                big.append((rel, os.path.getsize(p)))
            try:
                blob = io.open(p, "rb").read()
            except Exception as exc:
                unreadable.append((rel, str(exc)[:60]))
                continue
            hit = [f for f in forms if f.encode() in blob]
            if hit:
                bad.append((rel, "%d/%d forms, longest %d B"
                            % (len(hit), len(forms), max(len(f) for f in hit))))
            epn = dict((n, len(rx.findall(blob))) for n, rx in ep_pats)
            epn = dict((n, c) for n, c in epn.items() if c)
            if epn:
                ep_hits[rel.replace("\\", "/")] = epn
            rsn = dict((n, len(rx.findall(blob))) for n, rx in res_pats)
            rsn = dict((n, c) for n, c in rsn.items() if c)
            if rsn:
                ep_res[rel.replace("\\", "/")] = rsn
    # The ledger is NOT in the whitelist, so no exemption is needed: every fatal
    # hit is an offender. (If it were ever whitelisted, this would fail -- which
    # is the correct outcome, since the ledger cannot be edited to remove one.)
    offenders = dict(ep_hits)
    return bad, big, unreadable, ep_hits, ep_res, offenders


refresh()
removed = drop_caches_and_data()
sanitize_rsc()
cmd_scanned, cmd_rewritten, cmd_nonascii = normalize_cmd_endings()
write_docs()
prov_sha = write_provenance()
bad, big, unreadable, ep_hits, ep_res, ep_off = scan()

print("stage: %s" % STAGE)
print("provenance: STAGE_PROVENANCE.md sha256 %s" % prov_sha)
print("removed %d data/cache files (bytes not redistributed)" % len(removed))
print("cmd/bat: %d scanned, %d rewritten to CRLF+ASCII %s"
      % (cmd_scanned, len(cmd_rewritten), cmd_rewritten if cmd_rewritten else "-- none needed"))
if cmd_nonascii:
    sys.exit("stage NOT publishable: %d .cmd/.bat file(s) are not ASCII, and rewriting "
             "their bytes would be an unreadable edit: %s" % (len(cmd_nonascii), cmd_nonascii))
print("credential occurrences: %d %s" % (len(bad), bad if bad else "-- CLEAN"))
print("endpoint occurrences: %d file(s) %s"
      % (len(ep_hits), ep_hits if ep_hits else "-- CLEAN"))
print("residual occurrences, not gated (a port alone is NOT an endpoint, "
      "C-256; retired forms are unreachable by definition): %d file(s) %s"
      % (len(ep_res), ep_res if ep_res else "-- none"))
if ep_off:
    sys.exit("stage NOT clean: %d file(s) carry the live endpoint and are not the "
             "append-only ledger: %s" % (len(ep_off), sorted(ep_off)))
print("files over 90 MB: %d %s" % (len(big), big if big else "-- CLEAN"))
print("files the gate could not read: %d %s (an unread file is NOT a clean file)"
      % (len(unreadable), unreadable if unreadable else "-- none"))

# A gate that cannot fail is not a gate: exit non-zero so a caller cannot mistake this
# for a pass. Unreadable files fail too -- "my instrument failed" is not "clean".
if bad or unreadable:
    sys.exit("stage NOT clean: %d credential occurrence(s), %d unreadable file(s)"
             % (len(bad), len(unreadable)))

# two independent requirements, each of which must hold on its own
assert not bad, "CREDENTIAL PRESENT IN STAGE: %s" % bad
assert not big, "FILE OVER GITHUB'S LIMIT: %s" % big

n = sum(len(f) for _d, _s, f in os.walk(STAGE))
tot = sum(os.path.getsize(os.path.join(dp, f))
          for dp, _dn, fns in os.walk(STAGE) for f in fns)
print("stage contents: %d files, %.1f MB" % (n, tot / 1e6))
print("AWAITING EXPLICIT PUSH -- no git command has been run by this script")
