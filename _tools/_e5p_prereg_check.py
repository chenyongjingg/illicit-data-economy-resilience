# -*- coding: utf-8 -*-
"""Check the landed E5p artefact against the C-173 pre-registration AS AMENDED
by C-178 (amendment written 2026-09-24 04:32Z, before the artefact existed).

Written before the artefact exists, which is what makes it a check rather than
a description. Each reading is printed as PREDICTED / OBSERVED / VERDICT and the
script refuses to narrate a summary.

WHY P4 CHANGED (C-178). As first registered, P4 said `n_where_leq_differs_from_gt`
must stay 294. That was transcribed from an ORPHANED field: the old artefact has
no `n_stored_equals_gt` key while the current writer emits one at :713, and the
writer says at :699-703 that the previous revision returned the stored-vs-gt
count under this name. So the old 294 is a different quantity's reading and is
no baseline at all. The independence P4 was guarding is instead established by
source: n_exact uses `np.allclose(stored, by_le[True])` (:692) while n_leq_ne_gt
uses `np.array_equal(by_le[True], by_le[False])` (:704) -- two comparisons over
two operand sets. Replaced by a STRUCTURAL prediction (the key must exist) and a
DIRECTIONAL one (stored carries the <= t0 window, so it must NOT equal the > t0
recompute; a high value is a leak signal).

AND P1 HAS AN UNSTATED DEPENDENCY. :675-676 skips rows with no edges in either
frame, but :708 sets n = 300 regardless and :710 defines n_mismatch = n - n_exact
-- so a skipped row lands in n_mismatch as if it were a defect. If any such row is
sampled, n_exact_match CANNOT reach 300 however good the fix is. Hence the
discriminator below: 299 + empty first_mismatches is a SKIP, not a failure.

Exit codes: 0 = all predictions as registered, 1 = at least one mismatch,
2 = the artefact or a required field is absent (a statement about the
filesystem, not about the science).
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT = r"D:\CIS\results\53_E5p_result.json"
path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT

if not os.path.exists(path):
    print("ABSENT: %s" % path)
    print("This is a statement about the FILESYSTEM. It is not a reading.")
    sys.exit(2)

art = json.load(io.open(path, encoding="utf-8"))
try:
    ff = art["leakage_check"]["feature_filter_verification"]
    summ = art["leakage_check"]["summary"]
except (KeyError, TypeError) as e:
    print("MALFORMED: cannot reach leakage_check.feature_filter_verification (%s)" % e)
    print("Present top-level keys: %s" % sorted(art.keys()))
    sys.exit(2)

print("artefact: %s" % path)
print("status:   %r   seconds_total: %s" % (art.get("status"), art.get("seconds_total")))
print()

bad = []

print("--- P1/P2/P3 (C-173 as registered) ---")
for name, obs, pred in (
        ("n_exact_match", ff.get("n_exact_match"), 300),
        ("n_mismatch", ff.get("n_mismatch"), 0),
        ("summary.feature_filter_verification_exact",
         summ.get("feature_filter_verification_exact"), True)):
    ok = (obs == pred)
    if not ok:
        bad.append(name)
    print("  %-40s pred=%-6s obs=%-6s %s" % (name, pred, obs, "OK" if ok else "**MISMATCH**"))

# P1's unstated dependency: 299 with an EMPTY mismatch list is a skip, not a defect.
n_ex, n_mm = ff.get("n_exact_match"), ff.get("n_mismatch")
fm = ff.get("first_mismatches") or []
if n_ex == 299 and n_mm == 1:
    if len(fm) == 0:
        print()
        print("  **P1 RESOLVED AS A SKIP, NOT A FAILURE.** 299/1 with first_mismatches")
        print("  EMPTY means the single un-exact row had no edges in either frame and was")
        print("  never compared (:675-676). The recompute path matched on every row it")
        print("  actually compared. Record this as a SUCCESS with the caveat stated,")
        print("  not as a partial failure.")
        bad.remove("n_exact_match") if "n_exact_match" in bad else None
    else:
        print()
        print("  P1 as 299/1 but first_mismatches is NON-EMPTY (%d row(s)) -> a real" % len(fm))
        print("  mismatch. The fix did not hit the true cause. Do NOT reinterpret as a skip.")

print()
print("--- P4a/P4b (C-178, replacing the withdrawn value prediction) ---")
if "n_stored_equals_gt" not in ff:
    print("  **P4a FAILED: `n_stored_equals_gt` ABSENT from the artefact.**")
    print("  The current writer emits this key at :713 and the old artefact lacks it, so")
    print("  its absence means the run did NOT execute the writer I patched. STOP and")
    print("  identify the object before reading anything else.")
    bad.append("n_stored_equals_gt-present")
else:
    used = ff["n_stored_equals_gt"]
    print("  P4a  key present: OK  (value %s)" % used)
    print()
    print("  P4b  direction: stored carries the `<= t0` window, so it must NOT equal the")
    print("       `> t0` recompute. A value near n_sampled would be a LEAK SIGNAL.")
    print("       n_sampled=%s  n_stored_equals_gt=%s" % (ff.get("n_sampled"), used))
    if used is not None and ff.get("n_sampled") and used >= 0.9 * ff["n_sampled"]:
        print("       ** P4b FAILED: near-saturated. Investigate as a leak, do NOT read")
        print("          this as a pass. **")
        bad.append("n_stored_equals_gt-high")

print()
print("--- context (readings, not predictions) ---")
for k in ("n_sampled", "n_compared", "n_where_leq_differs_from_gt",
          "frac_where_leq_differs_from_gt", "n_stored_equals_gt"):
    print("  %-38s %s" % (k, ff.get(k)))
print("  %-38s %s" % ("not_inert", summ.get("feature_filter_verification_not_inert")))
print("  %-38s %s" % ("all_filtered_on_step_le_t0",
                      summ.get("all_features_filtered_on_step_le_t0")))
print("  first_mismatches: %d row(s)" % len(fm))
for r in fm[:6]:
    print("    %s t0=%s stored=%s" % (str(r.get("address", ""))[:12], r.get("t0"),
                                      r.get("stored")))

print()
print("NOTE ON SCOPE: this verifies the VERIFIER on 300 sampled rows. It is not")
print("evidence about the six within-t0 GAPs -- those are separate fields, checked")
print("by 75_E5p_verify.py, and the two verdicts must be reported separately.")
print()
print("RESULT: %s" % ("all as pre-registered" if not bad
                     else "%d unmet: %s" % (len(bad), bad)))
sys.exit(1 if bad else 0)
