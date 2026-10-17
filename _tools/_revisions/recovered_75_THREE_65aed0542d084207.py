#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""75_E5p_verify.py -- verify a landed E5p result against the ev_require
predicate, rather than against the file's existence.

WHY THIS IS NOT "does 53_E5p_result.json exist". A file that exists and a run
that succeeded are different claims, and the project has already paid for
conflating them: `16_E5p_temporal_gnn.md` carried "Status: complete" for a JSON
that had never existed anywhere (C-127). Existence is checkable by `ls`; what
the report's numbers MEAN is not. This tool checks the latter.

THREE OUTCOMES, THREE EXIT CODES, NEVER ONE RETURN VALUE
    0  PASS     -- every required reading present, correctly typed, in range
    2  FAIL     -- the file parsed but the predicate does not hold
    3  ABSENT   -- no file (or unparseable): says NOTHING about the science

That separation is the whole point (discipline 24). "My instrument failed" and
"the object is absent" must not share a return value; nor may "absent" and
"present but bad".

TYPING IS A CHECK, NOT A FORMALITY. The E5p writer carries an explicit warning
against `json.dump(..., default=str)`, which "silently writes a string where a
number is expected". A predicate that accepts `"0.81"` would re-admit exactly
the defect the writer guards against, so every numeric reading is required to be
int or float, and `None` never counts as a reading.
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT = r"D:\CIS\results\53_E5p_result.json"
ARMS = ("mlp_feature_only", "graphsage", "tgn")
DELTAS = ("1", "3", "5")
MIN_ARMS_WITH_TWO_DELTAS = 2          # ">=2 Delta" in the ev_require predicate
CONTROL_BAND = 0.05
LEAK_FLOOR = 0.98

# Every leakage-summary boolean the writer produces, required to be literally True.
SUMMARY_REQUIRED = (
    "all_features_filtered_on_step_le_t0",
    "feature_filter_verification_exact",
    "feature_filter_verification_not_inert",
    "leak_control_reaches_1",
    "shuffled_control_at_chance",
    "no_lifetime_column_in_model_matrices",
    "variance_instrument_positive_control_is_1",
    "wf_num_timesteps_matches_nsteps",
    "delta1_equals_recurrence",
    "naive_provided_column_baseline_shows_the_leak",
)

FAILS: list[str] = []


def num(v):
    """A reading counts only if it is a real number. bool is an int in Python,
    so it is excluded explicitly -- `True` is not an AUC."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check(ok, label, observed):
    flag = "ok  " if ok else "FAIL"
    print("  [%s] %-58s %s" % (flag, label, observed))
    if not ok:
        FAILS.append(label)
    return ok


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    print("=" * 78)
    print("75_E5p_verify -- ev_require predicate")
    print("  target: %s" % path)
    print("=" * 78)

    if not os.path.exists(path):
        print("\nABSENT: no file at that path. This is a statement about the")
        print("        filesystem, NOT about the experiment.")
        return 3
    try:
        with io.open(path, encoding="utf-8") as fh:
            r = json.load(fh)
    except Exception as exc:                                  # noqa: BLE001
        print("\nUNPARSEABLE (%s: %s)" % (type(exc).__name__, exc))
        print("        Neither present-and-good nor absent. Do not report either.")
        return 3
    if not isinstance(r, dict):
        print("\nUNPARSEABLE: top level is %s, not an object" % type(r).__name__)
        return 3

    print("\nstatus=%r  seconds_total=%r" % (r.get("status"), r.get("seconds_total")))
    check(r.get("status") == "ok", "status == 'ok'", repr(r.get("status")))

    # ---- arms: >=2 of {1,3,5} each carrying a REAL number -------------------
    print("\n-- arms: numeric auc_test at >=2 of Delta in %s --" % (DELTAS,))
    arms = r.get("arms")
    check(isinstance(arms, dict), "arms is an object", type(arms).__name__)
    for name in ARMS:
        a = (arms or {}).get(name)
        if not isinstance(a, dict):
            check(False, "arm %s present" % name, "MISSING")
            continue
        by = a.get("by_delta") or {}
        got = {D: (by.get(D, {}).get("auc_test") if isinstance(by.get(D), dict)
                   else None) for D in DELTAS}
        # A value that is PRESENT but not a number is a DEFECT, not a gap. The
        # writer explicitly warns that `default=str` "silently writes a string
        # where a number is expected"; a predicate that accepts "0.81" would
        # re-admit exactly the bug it exists to catch. Absent/None is a gap --
        # allowed to exist, it just does not count toward coverage. The first
        # version of this file conflated the two and let a stringified AUC pass
        # (caught by the fixture test, not by review).
        malformed = {D: got[D] for D in DELTAS
                     if got[D] is not None and not num(got[D])}
        check(not malformed,
              "arm %-16s no non-numeric auc_test" % name,
              malformed if malformed else "none")
        numeric = [D for D in DELTAS if num(got[D])]
        check(len(numeric) >= 2,
              "arm %-16s numeric auc_test at >=2 deltas" % name,
              "%d/3 %s" % (len(numeric), {D: got[D] for D in DELTAS}))
        # a test split of size 0 would make every AUC meaningless
        ns = [by.get(D, {}).get("n") for D in DELTAS if isinstance(by.get(D), dict)]
        check(bool(ns) and all(num(n) and n > 0 for n in ns),
              "arm %-16s non-empty test split at every delta" % name, "n=%s" % (ns,))

    # ---- leakage controls ---------------------------------------------------
    print("\n-- leakage / admissibility --")
    lc = r.get("leakage_check")
    check(isinstance(lc, dict), "leakage_check present", type(lc).__name__)
    sm = (lc or {}).get("summary") or {}
    for k in SUMMARY_REQUIRED:
        check(sm.get(k) is True, "summary.%s is True" % k, repr(sm.get(k)))

    lck = ((lc or {}).get("leak_control") or {}).get("test_auc_by_delta") or {}
    check(bool(lck) and all(num(v) and v > LEAK_FLOOR for v in lck.values()),
          "leak_control reaches ~1.0 at every delta",
          {k: v for k, v in lck.items()})
    sh = ((lc or {}).get("shuffled_label_control") or {}).get("test_auc_by_delta") or {}
    check(bool(sh) and all(num(v) and abs(v - 0.5) < CONTROL_BAND
                           for v in sh.values()),
          "shuffled-label control sits at chance (%g)" % CONTROL_BAND,
          {k: v for k, v in sh.items()})
    ff = (lc or {}).get("feature_filter_verification") or {}
    check(num(ff.get("n_compared")) and ff.get("n_compared") > 0,
          "feature-filter verification actually compared rows",
          "compared=%r exact=%r mismatch=%r" % (
              ff.get("n_compared"), ff.get("n_exact_match"), ff.get("n_mismatch")))

    # ---- the leaking baseline must be PRESENT and marked INADMISSIBLE -------
    print("\n-- naive_leaking_baseline: present, demonstrably leaking, inadmissible --")
    nv = r.get("naive_leaking_baseline")
    check(isinstance(nv, dict), "naive_leaking_baseline present", type(nv).__name__)
    # `is False`, not falsy: a missing key would also be falsy, and "we forgot to
    # say" must not read the same as "we said no".
    check(nv.get("admissible") is False if isinstance(nv, dict) else False,
          "naive_leaking_baseline.admissible is exactly False",
          repr(nv.get("admissible") if isinstance(nv, dict) else None))
    nb = ((nv or {}).get("by_delta") or {}) if isinstance(nv, dict) else {}
    nv1 = nb.get("1", {}).get("auc_test") if isinstance(nb.get("1"), dict) else None
    check(num(nv1) and nv1 > LEAK_FLOOR,
          "and it does demonstrably leak (AUC>%g at delta 1)" % LEAK_FLOOR,
          repr(nv1))

    d1 = r.get("delta1_equals_recurrence") or {}
    check(d1.get("identical") is True, "delta1_equals_recurrence.identical",
          repr(d1.get("identical")))

    # ---- verdict ------------------------------------------------------------
    print("\n" + "=" * 78)
    if FAILS:
        print("FAIL -- %d check(s) did not hold:" % len(FAILS))
        for f in FAILS:
            print("   - %s" % f)
        print("The file parsed; the predicate does not hold. Report neither "
              "'done' nor 'absent'.")
        return 2
    print("PASS -- every required reading present, correctly typed, in range.")
    print("Numbers may now be transcribed into 16_E5p_temporal_gnn.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

