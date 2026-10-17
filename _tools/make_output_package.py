#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_output_package.py -- build the dated deliverable package.

    output/cis_sprint_<YYYYMMDD>/

Layout follows the D:\\KBS-final convention: a dated directory under output/,
a per-artefact SHA-256 manifest inside it, and a README that states what is
established and what is not.

The manifest is computed over the PACKAGE's own bytes, after copying, and then
verified by re-reading from disk. Computing it from the source tree instead
would hash files that are not the ones shipped.

Excluded, with reasons:
  __pycache__            build artefacts, not deliverables
  _logs/results_sync.tgz 29 MB transport container; its contents are already
                         here as results/, and it is reproducible from the pod
  *.pyc
  _tmp_*                 live scratch files. `59_E9_ocr_full.py` renders each
                         page to `results/59_ocr_full_text/_tmp_<issue>_<n>.png`
                         and removes it in a `finally`; if the package is built
                         while that job is mid-page, the in-flight PNG is still
                         on disk and 1.1 MB of transient would ship as if it
                         were an artefact. Skipping the prefix is what keeps the
                         package a function of the finished state only.
  .rsc_cache.json        runtime cache written into _tools/ by rsc.py. It holds
                         THREE keys -- host, ip, at -- i.e. a pod endpoint goes
                         into every copy of the package. It reached the package
                         because it is a DOTFILE and none of the tables below
                         had a dotfile rule: it shipped by construction, not by
                         oversight of one build. Measured 2026-09-24: eleven
                         copies under the tree, ten byte-identical naming the
                         DECOMMISSIONED pod, and the live one naming the current
                         pod -- which is why the cure is the exclusion below and
                         NOT sanitising the file: copying the live cache in
                         would swap a retired endpoint for a live one and the
                         leak would look repaired. See ledger C-243 (same class,
                         `_tools/rsc.py`), C-247.

ONE file is transformed rather than copied: `code/_tools/rsc.py`. The live
transport must KEEP its compiled-in defaults to work, so the file that dials
the pod and the file that ships cannot be the same bytes -- and shipping the
live one put the pod password and the pod host into every copy of the
package. `sanitise_transport` rewrites the shipped copy to require them from
the environment, taking the replacement text from artefacts that already
carry the sanctioned form and every needle from the live file by AST, so
this generator removes a credential without ever containing one.
"""
from __future__ import annotations

import ast
import datetime as dt
import hashlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATE = dt.date.today().strftime("%Y%m%d")
# The README states both the package's date and its counts, and both are filled
# in from the build rather than typed: a hand-written date goes stale on the next
# rebuild in exactly the way a hand-written count does -- which is the defect the
# README's own header names instead of removing.
DATE_ISO = dt.date.today().isoformat()
PKG = os.path.join(ROOT, "output", "cis_sprint_%s" % DATE)

# (source relative to ROOT, destination relative to PKG)
TREES = [
    ("pipeline_reports", "pipeline_reports"),
    ("results", "results"),
    ("_server", "code/_server"),
    ("_tools", "code/_tools"),
]
FILES = [
    ("FINAL_SUMMARY.md", "FINAL_SUMMARY.md"),
    ("DELIVERY_README.md", "README.md"),
    ("_logs/results_manifest.sha256", "_logs/results_manifest.sha256"),
    ("_logs/results_manifest.diff.txt", "_logs/results_manifest.diff.txt"),
    # The two delivery-face documents. Until 2026-09-25 both existed ONLY inside
    # the re-cut packages (rc2/rc3/rc4) and nowhere in the working tree, so this
    # generator could not carry them and a fresh build silently dropped them --
    # "the delivery face is not a function of the tree", which is the class
    # ERRATA.md itself is about. They live at the tree root now and ship from
    # here like any other delivery file; see ledger C-376.
    ("ERRATA.md", "ERRATA.md"),
    ("OPERATIONS.md", "OPERATIONS.md"),
    # THE JUDGE SOURCE, and it is a .md on purpose (author's ruling 3, ledger
    # C-372). This item shipped the v5 `.docx` until 2026-09-25, which was wrong
    # three times over: v5 is VOID (plan v10's footer voids v5-v9); the tree has
    # no docx WRITER -- only readers -- so the package carried a superseded plan
    # in a format nothing here can regenerate; and v10 §二 requires the delivered
    # plan to be the bytes the plan's own citations resolve against. Shipping
    # v10's .md gives the delivery surface a live judge source for the first
    # time -- there is no "restore the old form" to fall back to.
    ("数据黑产韧性研究-冲刺计划书v10.md", "plan/数据黑产韧性研究-冲刺计划书v10.md"),
]
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_EXT = {".pyc"}
# ".rsc_cache.json" is a pod endpoint, and it is a DOTFILE -- which is why it
# rode into every earlier package. The rule that keeps it out is stated here,
# by class, not by patching one file; see the Excluded table above and C-247.
SKIP_FILES = {"results_sync.tgz", ".rsc_cache.json"}
SKIP_PREFIXES = ("_tmp_",)   # in-flight scratch renders; see module docstring

# Every dotfile this package is ALLOWED to contain. Empty on purpose: dotfiles
# are how a runtime cache, a credential, or an editor artefact gets in without
# any table above naming it. build() asserts the shipped tree matches this set,
# so the next such file fails the build instead of shipping.
ALLOWED_DOTFILES = set()


def sha(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_tree(src, dst):
    n = 0
    for dp, dns, fns in os.walk(src):
        # Hidden DIRECTORIES are excluded by class too: a `.cache/` or `.git/`
        # holds the same kind of non-deliverable as a dotfile, and no table
        # above names it. `.git` was already here; the rule now covers the rest.
        dns[:] = sorted(d for d in dns
                        if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(fns):
            if os.path.splitext(fn)[1] in SKIP_EXT or fn in SKIP_FILES:
                continue
            if fn.startswith(SKIP_PREFIXES):
                continue
            if fn.startswith(".") and fn not in ALLOWED_DOTFILES:
                continue
            sp = os.path.join(dp, fn)
            rel = os.path.relpath(sp, src)
            tp = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(tp), exist_ok=True)
            shutil.copy2(sp, tp)
            n += 1
    return n


def assert_no_dotfiles(dst):
    """The class rule's receipt: the SHIPPED tree is re-walked, not trusted.

    `copy_tree` filters as it goes, so a bug there is invisible from its return
    value -- the count of what it copied says nothing about what it should have
    skipped. This reads the package back off disk and fails the build if any
    dotfile or hidden directory is in it. Returns the number of files checked,
    so a caller can tell "clean" from "I walked nothing".
    """
    seen, bad = 0, []
    for dp, dns, fns in os.walk(dst):
        for d in dns:
            if d.startswith("."):
                bad.append(os.path.relpath(os.path.join(dp, d), dst) + "/")
        for fn in fns:
            seen += 1
            if fn.startswith(".") and fn not in ALLOWED_DOTFILES:
                bad.append(os.path.relpath(os.path.join(dp, fn), dst))
    if bad:
        raise SystemExit("REFUSING TO SHIP: %d dotfile/hidden entry(ies) in the "
                         "package -- add a rule, not a patch: %s"
                         % (len(bad), ", ".join(sorted(bad)[:10])))
    return seen


# ---------------------------------------------------------------------------
# The transport: `code/_tools/rsc.py`, rewritten rather than copied.

# field -> the published artefact whose sanitised block is authoritative for it.
# Read, not typed. `_repo_stage/_tools/rsc.py` carries HOST and PASS; PORT's
# sanitised form is not in the stage because the stage was not rebuilt after
# C-248 made PORT required -- it lives in rc4's shipped copy instead. Naming the
# sources makes the claim checkable: this package's transport blocks ARE those
# artefacts' blocks, byte for byte.
SANITISED_FROM = {
    "HOST": "_repo_stage/_tools/rsc.py",
    "PASS": "_repo_stage/_tools/rsc.py",
    "PORT": "output/cis_sprint_20260924_rc4/code/_tools/rsc.py",
}
TRANSPORT = "code/_tools/rsc.py"
# USER is deliberately NOT in that table. `root` is an account, not an endpoint
# and not a credential: it names nobody's host, and every sanctioned entry point
# sets it anyway. A default is removed when it points somewhere. Same rule as
# `_build_repo_stage.py:sanitize_rsc()`.


def _read(fp):
    with open(fp, encoding="utf-8", newline="") as fh:
        return fh.read()


def _binding(text, field):
    """The single module-level binding of `field`, or None. Position-based."""
    for node in ast.parse(text).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == field):
            return node
    return None


def _is_required(text, field):
    """True iff `field` is bound to `os.environ[...]` -- no default at all.

    Structural on purpose, so no spelling satisfies it: quotes, `getenv`, an
    extra wrapper all still have to BE a subscript of `os.environ`. This is the
    receipt's predicate, and it is stated over the class (a binding that has no
    default) rather than over one expected line.
    """
    node = _binding(text, field)
    if node is None:
        return False
    v = node.value
    if field == "PORT" and isinstance(v, ast.Call) and v.args:
        v = v.args[0]            # `int(os.environ[...])`
    return (isinstance(v, ast.Subscript)
            and isinstance(v.value, ast.Attribute)
            and v.value.attr == "environ"
            and isinstance(v.value.value, ast.Name)
            and v.value.value.id == "os")


def _default_of(text, field):
    """The compiled-in default `field` carries, as a VALUE, or None.

    The reason this reads the live file instead of naming a constant here: the
    tool whose job is to remove a credential is the one place it must not be
    copied to. `_build_repo_stage.py` states the same rule as "located by
    position, so no retired port literal is written here".
    """
    node = _binding(text, field)
    if node is None:
        return None
    for sub in ast.walk(node.value):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "get" and len(sub.args) >= 2
                and isinstance(sub.args[-1], ast.Constant)
                and isinstance(sub.args[-1].value, str)):
            return sub.args[-1].value
    return None


def _block(src, field):
    """The sanitised block for `field` in `src`: its assignment plus the comment
    lines directly above it, so the transplanted text is the whole documented
    form rather than a bare line."""
    text = _read(src)
    if not _is_required(text, field):
        raise SystemExit("REFUSING TO BUILD: %s is not sanitised for %s -- the "
                         "replacement text has to come from an artefact that "
                         "actually carries it" % (src, field))
    lines = text.split("\n")
    hits = [i for i, l in enumerate(lines) if l.startswith(field + " = ")]
    if len(hits) != 1:
        raise SystemExit("REFUSING TO BUILD: %d `%s = ` lines in %s"
                         % (len(hits), field, src))
    i = hits[0]
    j = i
    while j > 0 and lines[j - 1].startswith("#"):
        j -= 1
    return "\n".join(lines[j:i + 1])


def rewrite_transport(text):
    """Return (rewritten_text, report). PURE -- no disk, so it can be dry-run.

    Line endings are preserved: matched on an LF-normalised copy, restored to
    the file's own ending at the end. Rewriting a CRLF file into LF would be a
    byte-level change to every line of the file, which is not what this does and
    must not be left to look like what it does.
    """
    crlf = "\r\n" in text
    body = text.replace("\r\n", "\n")
    report = []
    for field in ("HOST", "PORT", "PASS"):
        lines = body.split("\n")
        hits = [i for i, l in enumerate(lines) if l.startswith(field + " = ")]
        if len(hits) != 1:
            raise SystemExit("REFUSING TO BUILD: %d `%s = ` lines in the shipped "
                             "transport, expected 1" % (len(hits), field))
        blk = _block(SANITISED_FROM[field], field).split("\n")
        lines[hits[0]:hits[0] + 1] = blk
        body = "\n".join(lines)
        report.append((field, SANITISED_FROM[field], len(blk)))
    if crlf:
        body = body.replace("\n", "\r\n")
    return body, report


def sanitise_transport(pkg):
    """Ship `code/_tools/rsc.py` with no compiled-in endpoint and no credential."""
    p = os.path.join(pkg, TRANSPORT)
    if not os.path.exists(p):
        raise SystemExit("REFUSING TO BUILD: transport absent from the package: %s" % p)
    live = _read(os.path.join(ROOT, "_tools", "rsc.py"))
    needles = [(f, _default_of(live, f)) for f in ("HOST", "PORT", "PASS")]
    missing = [f for f, v in needles if not v]
    if missing:
        raise SystemExit(
            "REFUSING TO BUILD: the LIVE transport already carries no compiled-in "
            "default for %s. That is the desired end state and it makes this "
            "transform a no-op -- so remove it deliberately (and record that the "
            "delivery no longer needs it) rather than leaving a security step that "
            "passes by doing nothing and saying nothing (C-242's family)."
            % ", ".join(missing))
    before = _read(p)
    after, report = rewrite_transport(before)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(after)
    back = _read(p)                      # the receipt, read back OFF DISK
    for field in ("HOST", "PORT", "PASS"):
        if not _is_required(back, field):
            raise SystemExit("REFUSING TO BUILD: shipped transport still lets %s "
                             "fall back to a default" % field)
    for field, value in needles:
        if value in back:
            raise SystemExit("REFUSING TO BUILD: the shipped transport still "
                             "contains the live %s default" % field)
    # The credential is the one needle that may not appear ANYWHERE in the
    # package; the host and port strings legitimately occur in notes and probes
    # (that distinction is C-247/C-248's, and it is the difference between a
    # string hit and a carrier).
    cred = _default_of(live, "PASS")
    hits = []
    for dp, dns, fns in os.walk(pkg):
        for fn in fns:
            q = os.path.join(dp, fn)
            try:
                if cred in _read(q):
                    hits.append(os.path.relpath(q, pkg).replace("\\", "/"))
            except (UnicodeDecodeError, OSError):
                pass
    if hits:
        raise SystemExit("REFUSING TO SHIP: the live credential appears in %d "
                         "packaged file(s): %s" % (len(hits), ", ".join(sorted(hits)[:8])))
    print("  transport %s: %d field(s) rewritten (HOST/PORT/PASS), %d -> %d B"
          % (TRANSPORT, len(report), len(before.encode("utf-8")),
             len(after.encode("utf-8"))))
    for field, src, n in report:
        print("    %-5s <- %s (%d-line block)" % (field, src, n))
    print("  transport receipt (read back from disk): endpoint defaults 0; "
          "live credential in package: 0 files (needles taken from the live "
          "file by AST, never written down here)")


def provenance(entries):
    """One line saying WHEN this package was built and FROM WHAT.

    WHY IT IS NEEDED. The package is a snapshot, and the tree it copies keeps
    moving after it is built -- the ledger is append-only and grows with every
    finding, and `results/` grows with every run. So "is this package current?"
    is otherwise unanswerable from inside the package: its own manifest is
    perfectly self-consistent while being out of date. That is the gap the
    E5p report and the README both fell into on 2026-09-24, in the same shape:
    a record that verifies against itself and says nothing about whether the
    world it describes has moved.

    Recording the SOURCE ledger's hash closes it cheaply and honestly. A reader
    recomputes it from the live tree; if it differs, this package predates later
    entries -- so the package is OLD rather than WRONG, and the reader knows
    which way to look. It does not make the package current; it makes its
    staleness DETECTABLE, which is the difference between a limit and a trap.
    """
    led = os.path.join(ROOT, "pipeline_reports", "progress.md")
    if not os.path.exists(led):
        return "built %s; source ledger ABSENT" % dt.datetime.now().isoformat(
            timespec="seconds")
    return ("built %s as %s; source pipeline_reports/progress.md = %s (%d bytes)"
            " -- if the live ledger's sha256 differs, this package predates later"
            " entries; if the directory name differs, this package has been moved"
            " (the packages are write-once, so a move means it is superseded)"
            % (dt.datetime.now().isoformat(timespec="seconds"),
               os.path.basename(PKG), sha(led), os.path.getsize(led)))


def main():
    if os.path.exists(PKG):
        print("refusing to overwrite an existing package: %s" % PKG)
        print("(packages are dated and immutable; remove it deliberately if you"
              " really mean to rebuild it)")
        return 2
    print("building %s" % PKG)
    total = 0
    for src, dst in TREES:
        sp = os.path.join(ROOT, src)
        if not os.path.isdir(sp):
            print("  SKIP (absent): %s" % src)
            continue
        n = copy_tree(sp, os.path.join(PKG, dst))
        print("  %-18s -> %-22s %4d files" % (src, dst, n))
        total += n
    for src, dst in FILES:
        sp = os.path.join(ROOT, src)
        if not os.path.exists(sp):
            print("  SKIP (absent): %s" % src)
            continue
        tp = os.path.join(PKG, dst)
        os.makedirs(os.path.dirname(tp), exist_ok=True)
        shutil.copy2(sp, tp)
        print("  %-18s -> %-22s  1 file" % (src, dst))
        total += 1

    # The transport: the one file that is REWRITTEN rather than copied. Done
    # here, before the manifest, so the hashed bytes are the shipped bytes.
    sanitise_transport(PKG)

    # README placeholders. The README states the package's own counts, and a
    # hand-written count is exactly the thing that goes stale on every rebuild --
    # the README said so itself ("if the two ever disagree, the header is
    # right") instead of removing the class. Substituting measured values removes
    # it. Done BEFORE the manifest so the hashed README is the shipped README,
    # and it FAILS if a placeholder is left behind: a template that silently does
    # not fill is the same defect as the CRLF manifest, which every reader's
    # `sha256sum -c` rejected while the writer's own check passed.
    rm = os.path.join(PKG, "README.md")
    if os.path.exists(rm):
        n_entries = sum(len(fns) for _, _, fns in os.walk(PKG))
        n_results = sum(len(fns) for _, _, fns in os.walk(os.path.join(PKG, "results")))
        # The ledger's own entry count. It shipped as a typed "78 distinct
        # correction ids" until 2026-09-25 -- a number with no predicate, which
        # no count over this tree reproduces (measured: 295 `^## C-` sections,
        # 284 distinct ids), i.e. exactly the class the paragraph above is about.
        # Counted over the PACKAGED ledger so the reader can check the number
        # against the bytes in front of them.
        n_ledger = 0
        lp = os.path.join(PKG, "pipeline_reports", "progress.md")
        if os.path.exists(lp):
            with open(lp, "r", encoding="utf-8", errors="replace") as fh:
                n_ledger = sum(1 for l in fh if l.startswith("## C-"))
        with open(rm, "rb") as fh:
            txt = fh.read().decode("utf-8")
        for token, val in (("@@N_ENTRIES@@", n_entries),
                           ("@@N_RESULTS@@", n_results),
                           ("@@N_LEDGER@@", n_ledger),
                           ("@@DATE_ISO@@", DATE_ISO)):
            if token not in txt:
                print("  README: placeholder %s absent -- refusing to build a "
                      "README whose counts are not filled" % token)
                return 2
            txt = txt.replace(token, str(val))
        with open(rm, "wb") as fh:                 # binary: preserve line endings
            fh.write(txt.encode("utf-8"))
        print("  README: filled %d entries / %d results" % (n_entries, n_results))

    # The class rule's receipt, read back off disk BEFORE the manifest exists --
    # so what is asserted is the tree that is about to be hashed, not a hash
    # that already agrees with itself.
    n_chk = assert_no_dotfiles(PKG)
    print("  dotfile census: 0 in %d files (rule: no dotfile ships unless "
          "ALLOWED_DOTFILES names it)" % n_chk)

    # manifest over the PACKAGE's own bytes
    man = os.path.join(PKG, "_MANIFEST.sha256")
    entries = []
    for dp, dns, fns in os.walk(PKG):
        # same rule as copy_tree: a hidden directory is not walked, so the
        # manifest cannot list a file the copier refused to ship.
        dns[:] = sorted(d for d in dns
                        if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(fns):
            fp = os.path.join(dp, fn)
            if os.path.abspath(fp) == os.path.abspath(man):
                continue
            entries.append((os.path.relpath(fp, PKG).replace("\\", "/"), sha(fp)))
    entries.sort()
    # newline="\n": see verify_results.py. A CRLF manifest cannot be checked
    # with `sha256sum -c`, which is the command the README tells the reader to
    # run; every one of the 229 entries fails with "FAILED open or read".
    with open(man, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# cis_sprint_%s -- per-artefact SHA-256\n" % DATE)
        fh.write("# %d entries; verify with:  sha256sum -c _MANIFEST.sha256\n"
                 % len(entries))
        fh.write("# %s\n" % provenance(entries))
        for rel, h in entries:
            fh.write("%s  %s\n" % (h, rel))
    print("\n  wrote _MANIFEST.sha256  (%d entries)" % len(entries))

    # verify by re-reading from disk
    bad = 0
    for rel, h in entries:
        if sha(os.path.join(PKG, rel.replace("/", os.sep))) != h:
            print("  MISMATCH %s" % rel)
            bad += 1
    print("  RE-VERIFY: %d entries, %d bad" % (len(entries), bad))
    sz = sum(os.path.getsize(os.path.join(dp, f))
             for dp, _, fns in os.walk(PKG) for f in fns)
    print("  package size: %.1f MB" % (sz / 1e6))
    print("PACKAGE_%s" % ("OK" if bad == 0 else "FAIL"))
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
