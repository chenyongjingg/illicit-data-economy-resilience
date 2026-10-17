#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pull_results_missing.py -- fetch the pod-only files under results/ into the
local results/ tree.

WHY THIS EXISTS
---------------
The delivery package is built from the LOCAL tree (`make_output_package.py`
walks `results/`).  Anything the pod produced but that was never pulled is
silently absent from the package -- and absence leaves no trace in the manifest,
because the manifest is computed over what is in the package, not over what
should be.  So this closes the pod->local gap on `results/` explicitly.

WHAT IT DOES NOT DO
-------------------
* It does not pull `_tmp_*`: those are a running job's scratch renders and are
  deleted by their producer's `finally`.  A `find` that catches one is a
  time-point artefact (C-116).
* It does not delete anything locally.
* It does not decide what is a deliverable.  It only makes local match pod.

USAGE
    python _tools/pull_results_missing.py            # list only (dry run)
    python _tools/pull_results_missing.py --pull
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RSC = os.path.join(ROOT, "_tools", "rsc.py")
REMOTE = "/root/cis/results"
LOCAL = os.path.join(ROOT, "results")
PY = sys.executable or "python"


def remote_listing():
    out = subprocess.run([PY, RSC, "exec",
                          "cd /root/cis && find results -type f -printf '%P\\n' | sort"],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace")
    lines = (out.stdout or "").splitlines()
    # drop the [rsc] banner line(s)
    return [l.strip() for l in lines if l.strip() and not l.startswith("[rsc]")]


def local_listing():
    got = set()
    for dp, _dns, fns in os.walk(LOCAL):
        for fn in fns:
            got.add(os.path.relpath(os.path.join(dp, fn), LOCAL).replace(os.sep, "/"))
    return got


def main():
    do_pull = "--pull" in sys.argv
    pod = remote_listing()
    loc = local_listing()
    print("pod results/: %d files   local results/: %d files" % (len(pod), len(loc)))

    missing = [f for f in pod if f not in loc]
    tmp = [f for f in missing if os.path.basename(f).startswith("_tmp_")]
    real = [f for f in missing if not os.path.basename(f).startswith("_tmp_")]

    print("pod-only            : %d  (%d of them _tmp_ scratch, skipped)"
          % (len(missing), len(tmp)))
    for f in tmp:
        print("   [skip _tmp_] %s" % f)

    if not real:
        print("nothing to pull; local results/ already covers the pod.")
        return 0

    tot = 0
    for f in real:
        print("   %s" % f)
    print("\n%d files to pull." % len(real))
    if not do_pull:
        print("dry run -- re-run with --pull to fetch them.")
        return 0

    fail = []
    for f in real:
        dst = os.path.join(LOCAL, f.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        r = subprocess.run([PY, RSC, "get", "%s/%s" % (REMOTE, f), dst],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        ok = os.path.exists(dst) and os.path.getsize(dst) > 0
        if ok:
            tot += os.path.getsize(dst)
        else:
            fail.append(f)
        print("   %-40s %s" % (f, "ok" if ok else "FAILED"))

    print("\npulled %d/%d files, %.1f KB" % (len(real) - len(fail), len(real), tot / 1e3))
    if fail:
        print("FAILED: %s" % fail)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
