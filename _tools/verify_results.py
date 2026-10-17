#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_results.py -- LOCAL-SIDE. Hash what arrived, diff it, then verify.

Three jobs, in this order, and the order matters:

  1. HASH every file under results/ and diff against the stored manifest.
     UNCHANGED / CHANGED / ADDED / REMOVED are reported separately.
     CHANGED or REMOVED is an ALARM: files under results/ are write-once, so
     any such line means the record and the tree disagree. That is a finding to
     reconcile by naming which object is wrong -- never a licence to overwrite
     the record.

  2. WRITE the new manifest and the diff report.

  3. VERIFY the extracted tree against the manifest it just wrote, by
     re-hashing from disk. Step 1 hashed the same bytes in the same process, so
     step 3 alone would be circular -- it is only worth anything because the
     bytes came in over SFTP and were unpacked by tar, i.e. through a path that
     this script did not compute.

Usage
  python _tools/verify_results.py            # diff + write + verify
  python _tools/verify_results.py --check    # verify only, do not write
"""
from __future__ import annotations

import hashlib
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
LOGS = os.path.join(ROOT, "_logs")
MAN = os.path.join(LOGS, "results_manifest.sha256")
DIFF = os.path.join(LOGS, "results_manifest.diff.txt")
_L: list[str] = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _L.append(s)


def sha(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(p):
    out = {}
    if not os.path.exists(p):
        return out
    with open(p, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.rstrip("\n")
            if not ln.strip():
                continue
            h, _, f = ln.partition("  ")
            if f:
                out[f.replace("\\", "/")] = h
    return out


def scan():
    out = {}
    for dp, dns, fns in os.walk(RES):
        dns.sort()
        for fn in sorted(fns):
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, ROOT).replace("\\", "/")
            out[rel] = sha(fp)
    return out


def main():
    check_only = "--check" in sys.argv
    log("=" * 78)
    log("verify_results -- LOCAL side")
    log("=" * 78)
    log("  tree: %s" % RES)

    # ★A COUNT IS NOT AN IDENTITY (2026-09-24). This header used to name the old
    # side only as "old manifest: N entries". Two different manifests can both
    # have N entries, so a diff that says UNCHANGED 207 beside a rewrite of a
    # DIFFERENT 207-entry manifest reads exactly the same. The old side is now
    # pinned by its own sha256, size and mtime, read BEFORE anything is written.
    # The counterpart in the package (`output/.../_logs/results_manifest.diff.txt`)
    # is written by a different run over a different tree: it carried `ADDED 114`
    # while this one carried `UNCHANGED 207`, and with both headers naming only
    # counts, neither record said which object it was a statement about.
    old_raw = b""
    if os.path.exists(MAN):
        with open(MAN, "rb") as fh:
            old_raw = fh.read()
    old_sha = hashlib.sha256(old_raw).hexdigest() if old_raw else "(absent)"
    old_mtime = (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(MAN)))
                 if os.path.exists(MAN) else "(absent)")

    old = read_manifest(MAN)
    new = scan()
    log("  old manifest: %d entries" % len(old))
    log("  old manifest identity: sha256 %s" % old_sha)
    log("    %d B, mtime %s -- the count does not identify it; this does."
        % (len(old_raw), old_mtime))
    log("  files on disk: %d" % len(new))

    unchanged = sorted(k for k in new if old.get(k) == new[k])
    changed = sorted(k for k in new if k in old and old[k] != new[k])
    added = sorted(k for k in new if k not in old)
    removed = sorted(k for k in old if k not in new)

    log("")
    log("  UNCHANGED %d" % len(unchanged))
    log("  ADDED     %d" % len(added))
    log("  CHANGED   %d%s" % (len(changed), "   <-- ALARM" if changed else ""))
    log("  REMOVED   %d%s" % (len(removed), "   <-- ALARM" if removed else ""))
    for k in changed:
        log("    CHANGED %s" % k)
    for k in removed:
        log("    REMOVED %s" % k)
    for k in added:
        log("    ADDED   %s" % k)

    if check_only:
        log("\n  --check: manifest not written")
        return 0 if not (changed or removed) else 2

    os.makedirs(LOGS, exist_ok=True)
    # newline="\n" is load-bearing: on Windows, text mode writes CRLF, and
    # `sha256sum -c` then reads the \r as part of every filename and fails on
    # all of them. Python's own reader hides this (universal newlines strip
    # \r), so the record would be verifiable only by the tool that wrote it.
    with open(MAN, "w", encoding="utf-8", newline="\n") as fh:
        for k in sorted(new):
            fh.write("%s  %s\n" % (new[k], k))
    log("")
    log("  wrote %s" % MAN)

    # step 3 -- re-verify by re-hashing from disk
    log("")
    log("  RE-VERIFY against the manifest just written:")
    want = read_manifest(MAN)
    bad = 0
    for k, h in want.items():
        fp = os.path.join(ROOT, k.replace("/", os.sep))
        if not os.path.exists(fp):
            log("    MISSING %s" % k)
            bad += 1
        elif sha(fp) != h:
            log("    MISMATCH %s" % k)
            bad += 1
    log("  %d entries checked, %d bad" % (len(want), bad))

    with open(DIFF, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(_L) + "\n")
    log("  wrote %s" % DIFF)
    log("VERIFY_%s" % ("OK" if bad == 0 and not (changed or removed) else "FAIL"))
    return 0 if bad == 0 and not (changed or removed) else 2


if __name__ == "__main__":
    sys.exit(main())
