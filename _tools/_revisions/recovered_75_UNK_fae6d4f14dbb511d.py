# -*- coding: utf-8 -*-
"""Mutation-test the NEW branches of 75_E5p_verify.py.

The ledger records a fixture suite (progress.md:3720) that named cases like
`FAIL_shuffled_control_off_chance`, but no such file was persisted -- so the
checks added on 2026-09-24 are untested. This builds them.

The schema is copied from the WRITER (53_E5p_temporal_gnn.py), not from the
predicate: the project has already been burned by a fixture written from the same
wrong mental model as the predicate it was meant to test (the `meta.deltas`
incident). The strongest test is the real artefact when it lands; this is the
cheap test that runs before it.

Each case states the outcome it EXPECTS, so a case that passes for the wrong
reason is visible.
"""
import io
import json
import os
import subprocess
import sys

TMP = r"C:\Users\33378\AppData\Local\Temp\e5p_fixtures"
VERIFY = r"D:\CIS\_tools\75_E5p_verify.py"
DELTAS = ["1", "3", "5"]
ARMS = ["mlp_feature_only", "graphsage", "tgn"]

SUMMARY_KEYS = (
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


def base():
    """A well-formed artefact that should PASS every check."""
    r = {
        "status": "ok",
        "seconds_total": 1234.5,
        "meta": {"deltas": [1, 3, 5]},
        "split": {"test": 123442, "train": 576059, "val": 123441},
        "arms": {},
        "leakage_check": {
            "summary": {k: True for k in SUMMARY_KEYS},
            "leak_control": {
                "test_auc_by_delta": {D: 0.999 for D in DELTAS},
                "test_within_t0_auc_by_delta": {D: {"weighted": 0.999} for D in DELTAS},
            },
            "shuffled_label_control": {
                "test_auc_by_delta": {D: 0.81 for D in DELTAS},
                "test_within_t0_auc_by_delta": {D: {"weighted": 0.50} for D in DELTAS},
                "selection_was_blinded_to_true_labels": True,
            },
            "feature_filter_verification": {"n_compared": 5000, "n_exact_match": 5000,
                                            "n_mismatch": 0,
                                            "n_where_leq_differs_from_gt": 900},
        },
        "naive_leaking_baseline": {"admissible": False,
                                   "by_delta": {D: {"auc_test": 1.0} for D in DELTAS}},
        "delta1_equals_recurrence": {"identical": True},
    }
    for name in ARMS:
        r["arms"][name] = {"by_delta": {}}
        for i, D in enumerate(DELTAS):
            r["arms"][name]["by_delta"][D] = {
                "auc_test": 0.80 + 0.01 * i,
                "n": 40000,
                "within_t0_auc": {"weighted": 0.75, "unweighted": 0.74},
            }
    return r


def mutate(r, case):
    """Return (mutated, expected_exit, why)."""
    if case == "PASS_baseline":
        return r, 0, "a well-formed artefact with a blinded, at-chance control"
    if case == "FAIL_pooled_control_off_0p5":
        # THE OLD BEHAVIOUR: pooled 0.81. The band must now IGNORE this and pass.
        r["leakage_check"]["shuffled_label_control"]["test_auc_by_delta"] = {
            D: 0.81 for D in DELTAS}
        return r, 0, ("pooled 0.81 with within-t0 0.50 -- must PASS now; if this "
                      "fails, the band is still on the pooled column")
    if case == "FAIL_control_not_at_chance_within_t0":
        r["leakage_check"]["shuffled_label_control"]["test_within_t0_auc_by_delta"] = {
            D: {"weighted": 0.81} for D in DELTAS}
        return r, 2, "within-t0 control 0.81 -- the real off-chance failure"
    if case == "FAIL_selection_not_blinded":
        r["leakage_check"]["shuffled_label_control"][
            "selection_was_blinded_to_true_labels"] = None
        return r, 2, "writer does not assert blind selection"
    if case == "FAIL_arm_does_not_clear_control":
        for D in DELTAS:
            r["arms"]["tgn"]["by_delta"][D]["within_t0_auc"]["weighted"] = 0.52
        return r, 2, "tgn within-t0 0.52 vs control 0.50 -- under MARGIN=0.05"
    if case == "FAIL_missing_within_t0_on_control":
        del r["leakage_check"]["shuffled_label_control"]["test_within_t0_auc_by_delta"]
        return r, 2, "control has no within-t0 block at all"
    if case == "FAIL_stringified_auc":
        r["arms"]["graphsage"]["by_delta"]["1"]["auc_test"] = "0.81"
        return r, 2, "a stringified AUC must not pass (default=str regression)"
    raise SystemExit("unknown case " + case)


CASES = [
    "PASS_baseline",
    "FAIL_pooled_control_off_0p5",
    "FAIL_control_not_at_chance_within_t0",
    "FAIL_selection_not_blinded",
    "FAIL_arm_does_not_clear_control",
    "FAIL_missing_within_t0_on_control",
    "FAIL_stringified_auc",
]


def main():
    if not os.path.isdir(TMP):
        os.makedirs(TMP)
    bad = 0
    for case in CASES:
        obj, want, why = mutate(base(), case)
        p = os.path.join(TMP, case + ".json")
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
        pr = subprocess.run([sys.executable, VERIFY, p],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
        got = pr.returncode
        ok = (got == want)
        if not ok:
            bad += 1
        print("%-4s %-38s exit=%-2s want=%-2s  %s"
              % ("ok" if ok else "BAD", case, got, want, why))
        if not ok:
            tail = [l for l in (pr.stdout or "").splitlines()
                    if l.strip().startswith("[FAIL]") or "FAIL --" in l]
            for l in tail[:6]:
                print("        " + l.strip())
    print("\n%d/%d cases behaved as declared" % (len(CASES) - bad, len(CASES)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

