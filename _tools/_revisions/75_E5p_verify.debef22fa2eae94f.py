#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""75_E5p_verify.py -- verify a landed E5p result against the ev_require
predicate, rather than against the file's existence.

WHY THIS IS NOT "does 53_E5p_result.json exist". A file that exists and a run
that succeeded are different claims, and the project has already paid for
conflating them: `16_E5p_temporal_gnn.md` carried "Status: complete" for a JSON
that had never existed anywhere (C-127). Existence is checkable by `ls`; what
the report's numbers MEAN is not. This tool checks the latter.

FIVE OUTCOMES, FIVE EXIT CODES, NEVER ONE RETURN VALUE
    0  PASS          -- every required reading present, correctly typed, in range
    2  FAIL          -- every reading present, and a VALUE violates the predicate
    3  ABSENT        -- no file (or unparseable): says NOTHING about the science
    4  INCOMPLETE    -- no value violates anything, but a required reading is
                        not IN THE RECORD, so it cannot be judged
    5  FAIL+INCOMPLETE -- BOTH at once: some value violates, and some readings
                        are absent. Neither is subordinate to the other.

That separation is the whole point (discipline 24). "My instrument failed" and
"the object is absent" must not share a return value; nor may "absent" and
"present but bad".

WHY 5 EXISTS (peer R65, 2026-09-24). 4 was reachable only when FAILS was empty,
so "one value failure" and "one value failure plus five gaps" both returned 2 --
the line-level distinction `check_reading` exists to preserve was discarded at
the verdict. That is the same doctrine violated one level up, and it mattered
immediately: the artefact a pre-fix writer produces trips a plain check (its own
`shuffled_control_at_chance` summary flag was computed on the POOLED column, so
it can be False), which would have returned 2 and made the GAPs look like the
science failing. A code is the one channel that cannot be read selectively, so
the combination gets its own.

WHY 4 EXISTS, ADDED 2026-09-24. The principle above was applied to the FILE but
not one level down, to FIELDS. A record that never wrote
`selection_was_blinded_to_true_labels` was reported with the same code as one
that wrote `False` -- so "this artefact predates the check" and "this artefact
fails the check" were indistinguishable. That is the same conflation this
docstring opens by forbidding, and it is not hypothetical: the run in flight on
2026-09-24 was produced by a writer WITHOUT those fields, so its artefact would
have been reported as a value failure. A record missing a field is a statement
about the RECORD; it licenses no claim about the experiment either way.

TYPING IS A CHECK, NOT A FORMALITY. The E5p writer carries an explicit warning
against `json.dump(..., default=str)`, which "silently writes a string where a
number is expected". A predicate that accepts `"0.81"` would re-admit exactly
the defect the writer guards against, so every numeric reading is required to be
int or float, and `None` never counts as a reading.

WHAT CHANGED ON 2026-09-24, AND WHY. This file used to test the shuffled-label
control's POOLED AUC against 0.5. Two things were wrong with that, and a peer
review surfaced both:

  1. The arms are reported on the within-t0 metric (`within_t0_auc`), whose own
     docstring says a pooled AUC "partly measures the calendar" because `room` is
     knowable at t0 and predicts on its own. So the arms and the control were
     never the same quantity, and the band was applied to the confounded side of
     that mismatch. A scorer that merely ranks by entry step -- learnable from
     features with no labels at all -- scores above 0.5 pooled. 0.5 is not this
     evaluation's no-skill floor; the control's own reading is.
  2. The control's checkpoint was selected on TRUE validation labels while it was
     trained on permuted ones, so its model was chosen by the answer it had to be
     blind to (it rose monotonically, 0.79579 -> 0.83927, across five epochs).
     That is fixed in the writer; this file now requires the writer to say so via
     `selection_was_blinded_to_true_labels`.

The chance band now applies to the within-t0 value, and the pooled value is still
required to be PRESENT (it is a real reading) but is no longer asserted against
0.5. A third check was added that the file previously could not make: every arm
must clear the control by MARGIN on that shared metric.
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
# How far an arm must clear the control on the control's own metric. Comparing
# an arm to 0.5 answers "better than nothing at all"; comparing it to the control
# answers "better than this pipeline's own no-skill floor", which is the question
# the plan's claim actually needs.
MARGIN = 0.05

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

FAILS: list[str] = []      # a reading is present and violates the predicate
MISSING: list[str] = []    # the reading is not in the record at all


def num(v):
    """A reading counts only if it is a real number. bool is an int in Python,
    so it is excluded explicitly -- `True` is not an AUC."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def wtd(blk):
    """Weighted within-t0 AUC per delta from a control block, or {} if absent.

    `within_t0_auc` returns a dict (weighted / unweighted / per-bin); the arms
    carry it inside `by_delta[D].within_t0_auc`, the controls inside
    `test_within_t0_auc_by_delta[D]`. This is the metric the arms are judged on,
    so it is the metric the control has to be judged on too.
    """
    src = (blk or {}).get("test_within_t0_auc_by_delta") or {}
    return {k: (v or {}).get("weighted") for k, v in src.items()}


def check(ok, label, observed):
    flag = "ok  " if ok else "FAIL"
    print("  [%s] %-58s %s" % (flag, label, observed))
    if not ok:
        FAILS.append(label)
    return ok


def check_reading(absent, ok, label, observed):
    """A reading that is NOT IN THE RECORD is a different verdict from a reading
    that is in the record and wrong. `absent` wins when both would apply."""
    if absent:
        print("  [GAP ] %-58s %s" % (label, observed))
        MISSING.append(label)
        return False
    return check(ok, label, observed)


def no_values(d):
    """True when a per-delta block carries no usable reading at all."""
    return not d or all(v is None for v in d.values())


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
          "leak_control reaches ~1.0 at every delta (pooled)",
          {k: v for k, v in lck.items()})
    # The same requirement on the unconfounded metric. A leak that showed up only
    # in the pooled column would be a calendar artefact rather than a leak.
    lcw = wtd((lc or {}).get("leak_control"))
    check_reading(no_values(lcw),
                  bool(lcw) and all(num(v) and v > LEAK_FLOOR for v in lcw.values()),
                  "leak_control reaches ~1.0 at every delta (within-t0)", lcw)

    ctl = (lc or {}).get("shuffled_label_control") or {}
    shp = ctl.get("test_auc_by_delta") or {}
    shw = wtd(ctl)
    # The chance band applies to the WITHIN-STEP value, not the pooled one.
    # `within_t0_auc`'s own docstring says a pooled AUC "partly measures the
    # calendar", and the arms are reported on the within-t0 metric -- so the
    # pooled control and the arm numbers were never the same quantity, and 0.5
    # is not the pooled column's null. The pooled value is still a real reading,
    # so it is PRINTED, but it is not asserted against 0.5.
    check_reading(not shp,
                  bool(shp), "shuffled-label control reports a pooled reading too",
                  {k: v for k, v in shp.items()})
    print("  [info] pooled control is NOT tested against 0.5 -- see metric_note")
    # A control whose model was chosen by the answer it had to be blind to is not
    # a control, whatever its numbers look like. `is True`, not truthy: a missing
    # key must not read the same as "we did it".
    # A writer that never wrote this key is not the same as one that wrote False.
    # `is True`, not truthy, so `None` never reads as "we did it" -- but which of
    # the two it is decides whether this is a GAP or a FAILURE.
    blind = ctl.get("selection_was_blinded_to_true_labels", "<not recorded>")
    check_reading(blind == "<not recorded>", blind is True,
                  "control's checkpoint selection was blind to the true labels",
                  repr(blind))
    check_reading(no_values(shw),
                  bool(shw) and all(num(v) and abs(v - 0.5) < CONTROL_BAND
                                    for v in shw.values()),
                  "shuffled-label control at chance within-t0 (%g)" % CONTROL_BAND,
                  shw)
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
    # `is False`, not falsy -- and the missing case is now a GAP rather than a
    # FAILURE, which is what the old comment here said it wanted but the code
    # could not express: "we forgot to say" and "we said no" are different.
    _adm = nv.get("admissible", "<not recorded>") if isinstance(nv, dict) \
        else "<not recorded>"
    check_reading(_adm == "<not recorded>", _adm is False,
                  "naive_leaking_baseline.admissible is exactly False", repr(_adm))
    nb = ((nv or {}).get("by_delta") or {}) if isinstance(nv, dict) else {}
    nv1 = nb.get("1", {}).get("auc_test") if isinstance(nb.get("1"), dict) else None
    check(num(nv1) and nv1 > LEAK_FLOOR,
          "and it does demonstrably leak (AUC>%g at delta 1)" % LEAK_FLOOR,
          repr(nv1))

    d1 = r.get("delta1_equals_recurrence") or {}
    check(d1.get("identical") is True, "delta1_equals_recurrence.identical",
          repr(d1.get("identical")))

    # ---- the arms must BEAT the control, on the control's own metric --------
    # This is the comparison the plan's claim needs, and until 2026-09-24 this
    # file could not make it: the arms were recorded on the within-t0 metric and
    # the control only on the pooled one, so there was no column in which the two
    # were the same quantity. Both sides are now within-t0 weighted.
    print("\n-- arms vs the shuffled-label control, same metric (within-t0) --")
    for name in ARMS:
        a = (arms or {}).get(name) or {}
        by = a.get("by_delta") or {}
        got = {D: ((by.get(D) or {}).get("within_t0_auc") or {}).get("weighted")
               for D in DELTAS}
        beats = {D: bool(num(got[D]) and num(shw.get(D))
                         and (got[D] - shw[D]) >= MARGIN)
                 for D in DELTAS if got[D] is not None}
        shown = {D: [round(got[D], 4) if num(got[D]) else got[D],
                     round(shw.get(D), 4) if num(shw.get(D)) else shw.get(D)]
                 for D in DELTAS}
        # An arm with no within-t0 anywhere, or a control with none, cannot be
        # compared -- that is a gap in the record, not a failing comparison.
        check_reading(all(got[D] is None for D in DELTAS) or no_values(shw),
                      bool(beats) and all(beats.values()),
                      "arm %-16s clears control by >=%g (arm,control)"
                      % (name, MARGIN), shown)

    # ---- verdict ------------------------------------------------------------
    print("\n" + "=" * 78)
    if FAILS and MISSING:
        # BOTH states at once. This gets its own code because the doctrine in
        # this file's own docstring -- distinct states must not share a return
        # value -- applies here too, and a caller watching only the code could
        # otherwise read "5 gaps and a value failure" as plain science failure.
        # Reported before the other two branches so the combination is not
        # silently collapsed into either one.
        print("FAIL+INCOMPLETE -- %d VALUE check(s) did not hold:" % len(FAILS))
        for f in FAILS:
            print("   - %s" % f)
        print()
        print("AND %d reading(s) are NOT IN THE RECORD at all:" % len(MISSING))
        for f in MISSING:
            print("   - %s" % f)
        print()
        print("Both states are present and neither is subordinate. The GAP lines")
        print("are not evidence about the experiment; the FAIL lines are. Read the")
        print("lines, not the code: this exit code means BOTH.")
        return 5
    if FAILS:
        print("FAIL -- %d VALUE check(s) did not hold:" % len(FAILS))
        for f in FAILS:
            print("   - %s" % f)
        print("Every required reading was present. The record is complete and the")
        print("predicate does not hold. Report neither 'done' nor 'absent'.")
        return 2
    if MISSING:
        print("INCOMPLETE -- %d required reading(s) are NOT IN THE RECORD:"
              % len(MISSING))
        for f in MISSING:
            print("   - %s" % f)
        print()
        print("This is a statement about the RECORD, NOT about the experiment.")
        print("Every value that IS present satisfied its check. A writer that")
        print("predates a check lands here, and so does a writer that silently")
        print("dropped a field -- the two are not distinguishable from here, and")
        print("neither licenses 'done' or 'absent'. Rerun with a writer that")
        print("emits these fields before any claim is made about the science.")
        return 4
    print("PASS -- every required reading present, correctly typed, in range.")
    print("Numbers may now be transcribed into 16_E5p_temporal_gnn.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
