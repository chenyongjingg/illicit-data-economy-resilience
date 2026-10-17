# -*- coding: utf-8 -*-
"""81_e5p_landing_check.py -- make the landing a COMPARISON, not a reading.

WHY THIS EXISTS
---------------
The landing produces a list of GAP and FAIL lines. Reading that list by eye is
how a missing line goes unnoticed and a present line gets explained away. The
expected set is known in advance (C-152), derived from the OLD WRITER'S own
source, so the landing can be an assertion: every GAP line must be one of the
predicted six, and every one of the six must appear.

WHITESPACE IS PART OF THE FORMAT
--------------------------------
The arm lines are built with `"arm %-16s clears control by >=%g (arm,control)"`
(75_:308), so the arm name is space-padded to 16. An exact-string comparison
would fail on PADDING rather than content -- a false alarm that looks like a
finding. So every line is whitespace-collapsed before comparison.

WHAT A FAIL LINE MEANS HERE (C-149 / C-154 / C-166)
---------------------------------------------------
A GAP is a reading that is NOT IN THE RECORD.

**A FAIL is dismissible only where the REASON reaches it.** The reason is about
HOW A FLAG IS COMPUTED: `shuffled_control_at_chance` is computed on the POOLED
column (old writer :1288-1290), which is confounded by t0 -- so it can be False
with no leak anywhere. That argument says NOTHING about
`feature_filter_verification_exact`, which is `bool(ff["n_mismatch"] == 0)`
(75_:1386) -- an agreement between stored features and a recomputation from the
raw CSVs. Dismissing it with the pooled argument is dismissing a flag by
association.

The first version of this file did exactly that: it had one argument and applied
it to the whole `summary.*` class, because a dismissal stated once reads as if it
covers everything on the line beneath it. So now the dismissal names the flags it
reaches (`POOLED_CONFOUNDED`), and every FAIL outside that set -- inside
`summary.*` or not -- is a finding.

TWO INDEPENDENT CLAIMS, TWO CODES, AND THEY MUST NOT SHARE ONE
-------------------------------------------------------------
There are two ways this check can end badly and they are not subordinate to each
other: (a) the GAP set is not what the record's source predicts; (b) a FAIL that
no dismissal reaches -- a genuine finding -- is present. A tool that prints (b)
but exits 0 is the defect I just fixed in 76_, where an unassessed delta printed
a warning and returned success. A code-only consumer cannot read either the
warning or the explanation, so the combination gets its own code:

    0  ruler clean, no finding, GAP set matches     (= PASS)
    2  a genuine finding, GAP set matches           (= FAIL)
    3  artefact absent                  (statement about the filesystem)
    4  no finding, GAP set does NOT match           (= INCOMPLETE)
    5  a genuine finding AND a GAP mismatch (neither is subordinate)
    6  THE RULER IS NOT THE RULER THE PREDICTION CAME FROM -- refuse to compare
    7  GAP set matches, but the RULER's verdict was nonzero (C-166)

WHY 7 EXISTS AND 0 NO LONGER MEANS "MATCH"
------------------------------------------
The GAP set matching the prediction means **the absence was PREDICTED**. It does
not mean the artefact is adequate -- the predicted set is six LICENSING READINGS
THAT ARE NOT IN THE RECORD. Returning 0 for that would hand a code-only consumer
"everything is fine", which is the opposite of what the lines say, and 75_'s own
footer states the rule this violates: "Read the lines, not the code: this exit
code means BOTH." So 0 now requires the ruler's code to be 0 as well, and the
state "my prediction held while the ruler did not pass" gets its own code instead
of being flattened into a pass.


Usage: 81_e5p_landing_check.py [--expect-sha <sha>] <artefact.json>
"""
import hashlib
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V75 = os.path.join(HERE, "75_E5p_verify.py")

# THE PREDICTION IS BOUND TO THE REVISION THAT PRODUCED IT.
# EXPECTED_GAPS below was derived by reading 75_ at this revision. If 75_ is
# edited, the labels and line numbers it was derived from stop being the labels
# and line numbers 75_ now emits -- and a comparison against an unbound ruler
# would silently track the edit and still report a match. So the ruler's own
# sha256 is pinned and asserted before it is used, and a mismatch is its own
# outcome rather than a pass. `--expect-sha` exists ONLY so the fixture suite can
# point the check at a stub; using it prints that the pin is not in force.
EXPECTED_V75_SHA = "debef22fa2eae94f"   # frozen ruler, 18,461 B

# Predicted from the old writer (55d7d8f8): it has test_within_t0_auc_by_delta
# 0 times and selection_was_blinded_to_true_labels 0 times, while the ARMS do
# carry within_t0_auc (eval_block :504) -- so the controls have no such column
# and the arm-vs-control comparison has nothing to compare against.
EXPECTED_GAPS = [
    "leak_control reaches ~1.0 at every delta (within-t0)",
    "control's checkpoint selection was blind to the true labels",
    "shuffled-label control at chance within-t0 (0.05)",
    "arm mlp_feature_only clears control by >=0.05 (arm,control)",
    "arm graphsage clears control by >=0.05 (arm,control)",
    "arm tgn clears control by >=0.05 (arm,control)",
]

# THE ONLY FLAGS THE POOLED-t0 ARGUMENT REACHES, NAMED ONE BY ONE (C-166).
# A dismissal has a domain. `shuffled_control_at_chance` is computed from the
# pooled AUC column, so "confounded by t0" applies to it. Nothing else in
# `summary.*` is computed that way -- `feature_filter_verification_exact` is an
# agreement between stored features and a recomputation from the raw CSVs, and
# `no_lifetime_column_in_model_matrices` is a column check. Listing the domain
# explicitly is the point: an argument stated once, under a heading that says
# `summary.*`, reads as covering every flag beneath it.
POOLED_CONFOUNDED = {
    # THE DISMISSAL IS BOUND TO THE WRITER THAT EARNED IT (C-172).
    #
    # The reason is "this flag is computed on the POOLED AUC column, which is
    # confounded by t0, so it can be False with no leak anywhere". That is true
    # of the OLD writer (:1288-1290) -- and only of it.
    #
    # The FIXED writer computes the SAME-NAMED flag from the WITHIN-t0 column
    # (:1401-1404), whose own comment says the pooled test "asked the wrong
    # question of the wrong quantity". So on the rerun the premise is FALSE: a
    # False there is a reading about the control, not an artefact of pooling.
    # Same field name, different quantity -- the C-168 failure, on a JSON field.
    #
    # Leaving this as one constant would make the tool dismiss, on the rerun, a
    # genuine finding -- C-166's defect (a dismissal reaching what it does not
    # cover) with the sign flipped. So it is keyed by prediction.
    "oldwriter": ("summary.shuffled_control_at_chance",),
    "fixedwriter": (),
}

# THE PREDICTION IS ABOUT A WRITER, SO THERE IS ONE PER WRITER (C-167).
#
# EXPECTED_GAPS above is the OLD writer's prediction: six readings ABSENT, because
# the old writer never computed within-t0 for either control.
#
# The rerun uses a FIXED writer -- one that computes within-t0 for both controls
# -- which changes exactly that, so its prediction is the EMPTY SET: all six
# present. Stated as a prediction BEFORE the artefact exists, and derived by
# reading a fixed writer, not by hoping:
#
# ★THE NAME IS NOT THE PIN (2026-09-24). This comment used to say "the FIXED
# writer (1ebf15e8)", and `1ebf15e8` is not the revision that produced rc4/rc5:
# that is `077cb379` (80,152 B). The label was two revisions stale while every
# value below it stayed correct, because the prediction is a PROPERTY ("the
# controls carry a within-t0 column") and not a revision -- any fixed writer
# yields the empty set. So the revision is deliberately NOT named here: a name
# that no code reads is the exact shape that misled a reader once already.
# The revision in force is carried by the artefact's OWN filename, which
# `80_e5p_landing.py:293` writes from the live writer's sha
# (`53_E5p_result.<sha16>.json`) -- a measurement, not a constant.
#   :1345  leak_control             gets test_within_t0_auc_by_delta
#   :1362  shuffled_label_control   gets test_within_t0_auc_by_delta
#   :1364  shuffled_label_control   selection_was_blinded_to_true_labels=True
# Those three close all six: the arm-vs-control GAPs need the control's within-t0
# column and nothing else, and until it existed there was no column in which the
# arms and the control were the same quantity.
#
# Without this, running the old prediction against the rerun's artefact reports
# "GAP SET DOES NOT MATCH" for the RIGHT outcome -- six gaps closed read as six
# missing. A prediction is bound to the object it was made about.
EXPECTED_GAPS_FIXED = []

# Labels state the PROPERTY the prediction was derived from, not a revision
# number, and name the writer's identity source. A revision literal here is
# read by nothing and was already stale once (see the note above EXPECTED_GAPS_FIXED).
PREDICTIONS = {
    "oldwriter": (EXPECTED_GAPS,
                  "a writer with NO within-t0 column on either control "
                  "[identity: the frozen 55d7d8f8 archive]: six readings ABSENT"),
    "fixedwriter": (EXPECTED_GAPS_FIXED,
                    "a writer that DOES compute within-t0 for both controls "
                    "[identity: the live writer's sha, in this artefact's own "
                    "name]: the six close, set EMPTY"),
}


def collapse(s):
    return re.sub(r"\s+", " ", s).strip()


def main():
    argv = sys.argv[1:]
    override = None
    if "--expect-sha" in argv:
        i = argv.index("--expect-sha")
        if i + 1 >= len(argv):
            print("--expect-sha needs a value")
            return 3
        override = argv[i + 1]
        del argv[i:i + 2]
    # Which prediction is in force. Default is the OLD writer's, so an invocation
    # that says nothing behaves as before.
    prediction = "oldwriter"
    if "--prediction" in argv:
        i = argv.index("--prediction")
        if i + 1 >= len(argv):
            print("--prediction needs a value (oldwriter | fixedwriter)")
            return 3
        prediction = argv[i + 1]
        del argv[i:i + 2]
    if prediction not in PREDICTIONS:
        print("unknown prediction %r; known: %s"
              % (prediction, ", ".join(sorted(PREDICTIONS))))
        return 3
    if not argv:
        print("usage: 81_e5p_landing_check.py [--expect-sha <sha>] "
              "[--prediction oldwriter|fixedwriter] <artefact.json>")
        return 3
    art = argv[0]
    if not os.path.exists(art):
        print("ABSENT -- nothing to check. Statement about the filesystem.")
        return 3

    # The pin is checked BEFORE the ruler is used, and a mismatch is its own
    # outcome. "I compared against a prediction derived from a different
    # revision" is a distinct claim from "the comparison did not match".
    if not os.path.exists(V75):
        print("RULER ABSENT: %s -- nothing was compared." % V75)
        return 6
    got_sha = hashlib.sha256(io.open(V75, "rb").read()).hexdigest()[:16]
    want_sha = override or EXPECTED_V75_SHA
    if override:
        print("NOTE: --expect-sha in force (%s); the frozen pin is NOT being"
              " enforced. For fixture use only.\n" % override)
    if got_sha != want_sha:
        print("RULER MISMATCH -- refusing to compare.")
        print("  the six GAP labels were derived by reading the ruler at %s"
              % want_sha)
        print("  the ruler now present is                        %s" % got_sha)
        print("  A comparison against any other revision is not the prediction;")
        print("  it would silently track whatever the edit changed.")
        return 6

    pr = subprocess.run([sys.executable, V75, art], capture_output=True,
                        text=True, encoding="utf-8", errors="replace")
    code = pr.returncode
    out = collapse(pr.stdout or "")

    gaps = [l for l in out.split("[GAP ]")[1:]]
    gaps = [g.split("[")[0].strip() if "[" in g else g.strip() for g in gaps]
    gaps = [g.split(" {")[0].split(" '")[0].strip() for g in gaps]

    fails = re.findall(r"\[FAIL\] ([^\[]+?)(?=\[|$)", out)

    print("75_E5p_verify on %s" % os.path.basename(art))
    print("  ruler sha256: %s%s"
          % (got_sha, "  (OVERRIDE -- pin NOT enforced)" if override else ""))
    print("  prediction : %s -- %s" % (prediction, PREDICTIONS[prediction][1]))
    print("  verdict code: %d" % code)
    print("  %d GAP line(s), %d FAIL line(s)\n" % (len(gaps), len(fails)))

    exp = [collapse(e) for e in PREDICTIONS[prediction][0]]
    seen_norm = [collapse(g) for g in gaps]
    missing = [e for e in exp if not any(s.startswith(e) for s in seen_norm)]
    unexpected = [s for s in seen_norm
                  if not any(s.startswith(e) for e in exp)]

    print("-- GAP set comparison (whitespace-collapsed) --")
    if not exp:
        print("  (the prediction is the EMPTY SET -- no reading was predicted to")
        print("   be missing, so any GAP line below is UNEXPECTED)")
    for e in exp:
        n = "PRESENT" if any(s.startswith(e) for s in seen_norm) else "MISSING"
        print("  %-8s %s" % (n, e))
    if unexpected:
        print("\n  UNEXPECTED GAP line(s) -- these were not predicted:")
        for u in unexpected:
            print("     %s" % u[:110])

    record_fails, finding_fails = [], []
    pooled_confounded = POOLED_CONFOUNDED[prediction]
    for f in fails:
        f = collapse(f)
        head = f.split(" is True")[0].strip()
        (record_fails if head in pooled_confounded else finding_fails).append(f)
    print("\n-- FAIL lines --")
    if not fails:
        print("  none")
    for f in record_fails:
        print("  RECORD    %s" % f[:100])
    for f in finding_fails:
        print("  FINDING   %s" % f[:100])
    if record_fails:
        print("\n  RECORD-only FAILs here are computed from the POOLED AUC column")
        print("  (old writer :1288-1290), which is confounded by t0 -- such a flag")
        print("  can be False with no leak anywhere. These, and only these:")
        for k in pooled_confounded:
            print("    - %s" % k)
    elif prediction == "fixedwriter":
        print("\n  No dismissal is in force for this prediction: the fixed writer")
        print("  computes `shuffled_control_at_chance` from the WITHIN-t0 column")
        print("  (:1401-1404), so the pooled-t0 argument does not reach it. A False")
        print("  here is a reading about the control, not a pooling artefact.")
    if finding_fails:
        print("\n  *** A FAIL no dismissal reaches IS a genuine finding. Read it. ***")

    ok = (not missing) and (not unexpected)
    print("\n" + "=" * 70)
    print(("GAP SET MATCHES THE '%s' PREDICTION" % prediction) if ok
          else ("GAP SET DOES NOT MATCH the '%s' prediction -- investigate "
                "before interpreting" % prediction))
    if finding_fails:
        print("AND a genuine finding is present (%d FAIL(s) no dismissal reaches)."
              % len(finding_fails))
    elif ok:
        print("and no finding that a dismissal fails to reach.")
    if finding_fails and ok:
        return 2
    if finding_fails:
        return 5
    if not ok:
        return 4
    # ok, and no finding. The GAP set matching means the ABSENCE WAS PREDICTED --
    # it is not a clean bill for the artefact. If the ruler still returned
    # nonzero, 0 would tell a code-only consumer "everything is fine" about a
    # record 75_ has just refused. That state gets 7, not 0.
    if code != 0:
        print("\n  But the RULER returned %d, not 0. A GAP set that matches the\n"
              "  prediction says the absence was PREDICTED, not that the artefact\n"
              "  is adequate -- so this is 7, not a pass (C-166)." % code)
        return 7
    return 0


if __name__ == "__main__":
    sys.exit(main())
