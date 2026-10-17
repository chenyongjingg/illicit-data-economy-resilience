# -*- coding: utf-8 -*-
"""E5p landing sequence -- run once the run reports RSC_EXIT.

WHY THIS IS A SCRIPT AND NOT A LIST OF COMMANDS I TYPE.

`53_E5p_temporal_gnn.py` hard-codes OUT_JSON (:174) and writes it once, at the
END of the run (:1308). So the moment the run finishes there is exactly one
window in which the old writer's artefact still exists, and the first thing that
happens in that window has to be the copy -- not a verification, not a smoke
test, not a look.

WHAT THE FIRST VERSION GOT WRONG (peer R66), AND WHY IT MATTERED.

Every check in it was a TRANSPORT check -- copy == original -- and a transport
check is equally true of a stale file. Two holes:

  1. The marker was PRINTED, never ASSERTED. It required `count >= 1`, so a log
     ending `RSC_EXIT=1` (a crashed run) passed the gate.
  2. Because OUT_JSON is written once at the end, a CRASH writes no new file and
     leaves whatever was already at that path. If a `--quick` smoke run had ever
     written there, a crashed full run would let this script archive the SMOKE
     artefact and print "is the same object as the artefact" -- under the label
     "the OLD writer's output", which is the only witness to what the unfixed
     control path produced. The label would have been false, and the sha256
     comparisons would all have passed, because they only say the copy equals
     the original.

So the gate now also asks the question the first version never asked: is the
thing copied the one THIS run produced?

  * marker must be exactly `RSC_EXIT=0` (a nonzero marker refuses);
  * the log must contain the writer's own end-of-run line, `wrote .../53_E5p_
    result.json` (:1311) -- a run that crashed before the write has no such line,
    so the artefact cannot be attributed to it;
  * after the pull, the artefact must parse, say `status == "ok"`, and carry the
    FULL run's configuration (`--expect-mlp-epochs`, default 20). The artefact
    records per-arm `epochs` derived from `args.mlp_epochs` (:1104), which is
    exactly what differs between a full run and a smoke run -- so this is the
    content-level binding, not another transport check.

Exits: 0 archived+verified, 3 the run has not finished cleanly, 4 mismatch or the
artefact is not this run's, 5 transport failed.
"""
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RSC = os.path.join(HERE, "rsc.py")
ART = "/root/cis/results/53_E5p_result.json"
ART_TXT = "/root/cis/results/53_E5p_result.txt"
ARCH = "/root/cis/results/53_E5p_result_oldwriter_55d7d8f8.json"
LOCAL = r"D:\CIS\results\_e5p_landing"
ROOT_RESULTS = os.path.join(os.path.dirname(HERE), "results")


def rsc(*args):
    pr = subprocess.run([sys.executable, RSC] + list(args),
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", cwd=HERE)
    return pr.returncode, (pr.stdout or "") + (pr.stderr or "")


def archive_once(src, arch):
    """Archive `src` to `arch` on the pod, DECIDING BEFORE TOUCHING ANYTHING.

    Returns (rc, pod_sha): 0 ok / 4 refuse or failed verification / 5 transport.

    Comparing AFTER the copy would report an overwrite that had already
    happened -- that is a receipt, not a guard. And a copy check only ever says
    "the copy equals the original"; it can NEVER detect that the destination was
    something else's. So the destination is read first, and an existing object
    is never overwritten: identical bytes are a no-op, differing bytes refuse.

    One function rather than two copies of the logic, because two copies drift
    and only one of them gets controlled.
    """
    rc, out = rsc("exec", "test -e %s && sha256sum %s || echo ABSENT"
                  % (arch, arch))
    if rc != 0:
        print("transport failed checking the archive name:\n%s" % out)
        return 5, None
    existing = None if "ABSENT" in out else (out.split()[0] if out.split() else None)

    rc, out = rsc("exec", "sha256sum %s" % src)
    if rc != 0 or not out.split():
        print("transport failed hashing the artefact:\n%s" % out)
        return 5, None
    src_sha = out.split()[0]

    if existing is not None:
        if existing == src_sha:
            print("already archived at %s with identical bytes -- not copying"
                  % arch)
            return 0, src_sha
        print("REFUSING TO OVERWRITE %s.\n"
              "  it holds sha256:%s\n"
              "  the artefact is sha256:%s\n"
              "An object already at this name is evidence. Pick another "
              "name with --archive, or establish what the existing file is."
              % (arch, existing[:16], src_sha[:16]))
        return 4, None

    rc, out = rsc("exec",
                  "cp -p %s %s && ls -l %s && sha256sum %s %s"
                  % (src, arch, arch, src, arch))
    if rc != 0:
        print("transport failed while archiving:\n%s" % out)
        return 5, None
    lines = [l for l in out.splitlines()
             if "  " in l and len(l.split()[0]) == 64]
    if len(lines) < 2:
        print("could not read two sha256 lines; NOT trusting this archive")
        return 4, None
    pod_a, pod_b = (l.split()[0] for l in lines[:2])
    if pod_a != pod_b:
        print("ARCHIVE MISMATCH: %s vs %s" % (pod_a[:16], pod_b[:16]))
        return 4, None
    print("archive verified: sha256:%s" % pod_a[:16])
    return 0, pod_a


def place_canonical(canon, raw):
    """(rc, line) -- write `raw` at the CANONICAL local name, never over an
    object that differs.

    The writer-derived archive is the immutable witness; the canonical name is
    what the driver reads, so the two serve different purposes and both must
    exist. But the canonical name is also the name an EARLIER run's output can
    already be sitting at -- the whole reason this step grew a guard. Identical
    bytes are a no-op; different bytes refuse, because an object at a name is
    evidence and "the file is there" is not the same claim as "the file is
    this run's".
    """
    h = hashlib.sha256(raw).hexdigest()
    if os.path.exists(canon):
        old = hashlib.sha256(io.open(canon, "rb").read()).hexdigest()
        if old == h:
            return 0, "canonical %s already holds these bytes (%s)" % (canon, h[:16])
        return 4, ("REFUSING to replace canonical %s: it holds sha256:%s and the "
                   "new object is sha256:%s. That file is evidence; move it to a "
                   "name that says what it is before placing this one."
                   % (canon, old[:16], h[:16]))
    tmp = canon + ".part"
    with io.open(tmp, "wb") as fh:
        fh.write(raw)
    back = io.open(tmp, "rb").read()
    if hashlib.sha256(back).hexdigest() != h:
        os.remove(tmp)
        return 4, "write-back check failed for %s -- nothing placed" % canon
    os.replace(tmp, canon)
    if hashlib.sha256(io.open(canon, "rb").read()).hexdigest() != h:
        return 4, "post-place check failed for %s" % canon
    return 0, "canonical placed: %s  sha256:%s" % (canon, h[:16])


def bind_text_report(txt, obj):
    """(ok, [lines]) -- do this text report and this artefact come from ONE run?

    Pure, so BOTH branches can be controlled on the old pair -- the only pair for
    which the answer is known independently, since one process wrote both.

    The two relations were measured on that pair (see step 5). The second is the
    one a stale text report fails: a text report left at the live name by an
    earlier run carries that earlier run's summary block.
    """
    out = []
    lc_sum = (obj.get("leakage_check") or {}).get("summary")
    secs = obj.get("seconds_total")
    if secs is None or lc_sum is None:
        return False, ["artefact lacks seconds_total / leakage_check.summary -- "
                       "cannot bind the text report to it"]
    m = re.search(r"runtime ([0-9.]+)s", txt)
    s = re.search(r"summary: (\{.*\})", txt)
    if not m or not s:
        return False, ["text report lacks `runtime`/`summary:` -- cannot bind it"]
    want_rt, got_rt = round(float(secs), 1), float(m.group(1))
    try:
        txt_sum = json.loads(s.group(1))
    except Exception as e:
        return False, ["the text report's summary block does not parse: %s" % e]
    same_summary = txt_sum == lc_sum
    out.append("content bind: txt runtime %s vs json seconds_total %.1f  -> %s"
               % (got_rt, want_rt, "OK" if got_rt == want_rt else "MISMATCH"))
    out.append("content bind: txt summary == json summary -> %s" % same_summary)
    ok = (got_rt == want_rt) and same_summary
    if not ok:
        out.append("the text report is NOT this run's -- it disagrees with the "
                   "artefact on the relations that hold on a genuine pair. NOT "
                   "labelling it as this run's output.")
    return ok, out


def gate(text, art=ART):
    """(ok, reason). Reads a log body; no transport involved, so it can be run
    against a preserved log as a fixture."""
    codes = re.findall(r"RSC_EXIT=(\d+)", text)
    if not codes:
        return False, ("no RSC_EXIT -- a log that exists is not a run that "
                       "happened; the terminal marker is the only thing that "
                       "says the run ended")
    if codes[-1] != "0":
        return False, ("RSC_EXIT=%s -- the run FAILED. Its log is the first "
                       "thing to read, not an artefact to archive" % codes[-1])
    if not re.search(r"wrote\s+%s" % re.escape(art), text):
        return False, ("the log never shows `wrote %s` -- this run did not reach "
                       "its own write step, so whatever is at that path was left "
                       "by an EARLIER run. Archiving it would mislabel it as this "
                       "run's output" % art)
    return True, "RSC_EXIT=0 and the writer's own `wrote` line is present"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="/root/cis/logs/53_full.log",
                    help="remote log path, or a local file to test the gate on")
    ap.add_argument("--local-log", action="store_true",
                    help="treat --log as a local file and only run the gate")
    ap.add_argument("--expect-mlp-epochs", type=int, default=20)
    ap.add_argument("--archive", default=None,
                    help="remote path to archive the artefact under. Default: "
                         "derived from the WRITER's own sha256 on the pod "
                         "(53_E5p_result.<sha16>.json), so a later run cannot "
                         "collide with an earlier run's archive name.")
    ap.add_argument("--writer", default="/root/cis/scripts/53_E5p_temporal_gnn.py",
                    help="pod path of the writer, used to name the archive")
    ap.add_argument("--artefact", default=ART,
                    help="pod path of the artefact to archive. Override ONLY to "
                         "control the archive guard against a known object; the "
                         "real landing always uses the default.")
    ap.add_argument("--artefact-txt", default=ART_TXT,
                    help="pod path of the TEXT report to archive. Same override "
                         "caveat as --artefact.")
    ap.add_argument("--skip-gate", action="store_true",
                    help="skip the run-completion gate. For CONTROLLING the "
                         "archive guard in isolation (its three branches need a "
                         "real artefact, which only exists after a run). Never "
                         "use this for a real landing -- it is the one thing "
                         "that binds the artefact to the run that wrote it.")
    a = ap.parse_args()
    if a.skip_gate:
        print("!! --skip-gate: the run-completion gate is OFF. This exercises "
              "the archive guard only; it does NOT establish that the artefact "
              "belongs to any run.")

    # ---- 0. the gate, on a local fixture -----------------------------------
    if a.local_log:
        text = io.open(a.log, encoding="utf-8", errors="replace").read()
        ok, why = gate(text, a.artefact)
        print("%s  %s" % ("GATE OPEN " if ok else "GATE SHUT ", why))
        return 0 if ok else 3

    # ---- 1. the gate, on the pod -------------------------------------------
    if not a.skip_gate:
        rc, out = rsc("exec", "cat %s" % a.log)
        if rc != 0:
            print("transport failed reading the log:\n%s" % out)
            return 5
        ok, why = gate(out, a.artefact)
        if not ok:
            print("REFUSING TO ARCHIVE -- %s" % why)
            return 3
        print("gate: %s" % why)

    # ---- 2. ARCHIVE FIRST, AND NEVER OVER AN ARCHIVE -----------------------
    #
    # This step used to be an unconditional `cp -p ART ARCH` under a FIXED name
    # (53_E5p_result_oldwriter_55d7d8f8.json). That was safe exactly once. The
    # old writer's artefact is now ALREADY at that name, so a second landing
    # would overwrite the only witness to what the unfixed control path produced
    # -- and would file THIS run's artefact under the OLD writer's name. Both
    # sha256 comparisons would still pass, because they only ever said "the copy
    # equals the original". A copy check can never detect that the destination
    # was something else's.
    #
    # So: the archive name is derived from THIS run's writer, and an existing
    # archive is never overwritten. Re-running is idempotent when the bytes are
    # already identical, and refuses when they are not.
    if a.archive:
        arch = a.archive
    else:
        rc, out = rsc("exec", "sha256sum %s" % a.writer)
        if rc != 0 or len(out.split()) < 1:
            print("cannot read the writer's sha; refusing to invent a name:\n%s"
                  % out)
            return 5
        wsha = out.split()[0]
        arch = "/root/cis/results/53_E5p_result.%s.json" % wsha[:16]
        print("archive name derived from THIS run's writer: %s" % arch)

    # DECIDE BEFORE TOUCHING ANYTHING (see archive_once).
    rc, pod_a = archive_once(a.artefact, arch)
    if rc != 0:
        return rc

    # ---- 3. pull it --------------------------------------------------------
    if not os.path.isdir(LOCAL):
        os.makedirs(LOCAL)
    dst = os.path.join(LOCAL, os.path.basename(arch))
    rc, out = rsc("get", arch, dst)
    if rc != 0 or not os.path.exists(dst):
        print("transport failed pulling the archive:\n%s" % out)
        return 5
    raw = io.open(dst, "rb").read()
    h = hashlib.sha256(raw).hexdigest()
    print("\nlocal %d B  sha256:%s  pod sha256:%s"
          % (len(raw), h[:16], pod_a[:16]))
    if h != pod_a:
        print("MISMATCH -- do not analyse this file")
        return 4

    # ---- 4. is this artefact THIS run's? (content, not transport) ----------
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception as e:
        print("archived file does not parse: %s" % e)
        return 4
    if obj.get("status") != "ok":
        print("artefact status=%r -- not a completed run" % obj.get("status"))
        return 4
    ep = ((obj.get("arms") or {}).get("mlp_feature_only") or {}).get("epochs")
    print("content: status=ok  mlp_feature_only.epochs=%r  seconds_total=%r"
          % (ep, obj.get("seconds_total")))
    if ep != a.expect_mlp_epochs:
        print("epochs=%r != expected %d -- this artefact did NOT come from a full "
              "run (a --quick smoke run writes a different value here). NOT "
              "labelling it as this run's output." % (ep, a.expect_mlp_epochs))
        return 4
    # ---- 5. the TEXT report: same guard, and a CONTENT bind to the JSON -----
    #
    # The writer writes OUT_TXT at the very END (:1588) with NO `wrote` log line
    # of its own, so the run-completion gate cannot reach it the way it reaches
    # the JSON. And unlike the JSON, the old text report has ALREADY been moved
    # aside on the pod, so the rerun's write lands on the live name -- and the
    # local copy at results/53_E5p_result.txt was the OLD run's text under the
    # live name until it was renamed. That is the hazard this step exists for.
    #
    # So the bind is CONTENT, in the same style as the epochs check above, not
    # another transport check. Both relations below were measured on the old
    # pair, with both files in hand:
    #   * the txt's `runtime %.1fs` == round(json.seconds_total, 1)
    #   * the txt's `summary: {...}` block == json.leakage_check.summary (dicts)
    # A stale text report at the live name fails the second one.
    arch_txt = re.sub(r"\.json$", ".txt", arch)
    if arch_txt == arch:
        arch_txt = arch + ".txt"
    rc, pod_t = archive_once(a.artefact_txt, arch_txt)
    if rc != 0:
        return rc
    dst_t = os.path.join(LOCAL, os.path.basename(arch_txt))
    rc, out = rsc("get", arch_txt, dst_t)
    if rc != 0 or not os.path.exists(dst_t):
        print("transport failed pulling the text report:\n%s" % out)
        return 5
    raw_t = io.open(dst_t, "rb").read()
    h_t = hashlib.sha256(raw_t).hexdigest()
    print("\nlocal %d B  sha256:%s  pod sha256:%s"
          % (len(raw_t), h_t[:16], pod_t[:16]))
    if h_t != pod_t:
        print("MISMATCH -- do not analyse this file")
        return 4

    okb, lines = bind_text_report(raw_t.decode("utf-8", "replace"), obj)
    for l in lines:
        print(l)
    if not okb:
        return 4

    # ---- 6. place at the CANONICAL local names -----------------------------
    #
    # run_pipeline.py:66 gates E5 on `ev=["results/53_E5p_result.json"]` -- the
    # canonical name, NOT the writer-derived archive name this script pulls to.
    # So the archive alone leaves the driver reading a path that does not exist.
    # The archive is the immutable witness; the canonical name is what the
    # driver reads. Both, and the canonical placement is guarded the same way,
    # because that is also the name an earlier run's output can already sit at
    # -- which it did: results/53_E5p_result.txt held the OLD run's text under
    # the live name until it was renamed to .oldwriter_55d7d8f8.txt.
    print("")
    for src_local, canon in ((dst, os.path.join(ROOT_RESULTS, "53_E5p_result.json")),
                             (dst_t, os.path.join(ROOT_RESULTS, "53_E5p_result.txt"))):
        rc, line = place_canonical(canon, io.open(src_local, "rb").read())
        print(line)
        if rc != 0:
            return rc

    print("\nOK -- this is the completed full run's artefact, archived before "
          "anything could overwrite it.")
    print("next: python 75_E5p_verify.py \"%s\"   (read the LINES)" % dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
