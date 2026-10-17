# -*- coding: utf-8 -*-
"""The t0 channel's CEILING, computed two ways that fail differently.

A scorer that is constant within each t0 bin cannot do better, on the POOLED
metric, than one that outputs the bin's own positive rate. Then a positive
strictly outranks a negative iff its bin's rate is higher, so

    AUC = [ sum_{i!=j} npos_i * nneg_j * 1{rate_i > rate_j}
            + 0.5 * sum_i npos_i * nneg_i ] / (Npos * Nneg)

WHY THERE ARE TWO IMPLEMENTATIONS HERE.

The closed form above was written first and it was WRONG. The bin table is a
list of (n, npos, rate) triples; the term `nneg_i` was built as `n - npos` and
then summed as if it were `n`, so the denominator came out as
`sum(nneg) - sum(npos)` instead of `sum(nneg)`. At Delta=5 that is 93,597
against a true 105,093, which inflated the ceiling by +0.045 -- enough to
reverse the conclusion. It was caught only because a second implementation was
built from the population instead of from the algebra, and the two disagreed.

So both are kept and required to agree. They do not share a failure mode: the
closed form can miscount a term, the rank version can mis-build a population,
and neither error is invisible to the other. Agreement here is evidence;
agreement between two copies of one formula would not be.

WHAT IT IS FOR. The ceiling is the maximum pooled AUC attainable by any score
that is a FUNCTION OF t0 ALONE (constant within a bin, bins ordered by positive
rate). So a control whose pooled AUC EXCEEDS this ceiling is not t0-only: its
scores do vary WITHIN bins.

**A POSITIVE RESIDUAL DOES NOT BOUND THE WITHIN-BIN AUC FROM BELOW (C-172).**
This file used to finish that sentence with "hence its within-t0 AUC must be
measurably above 0.5, so (pooled ~0.84, within-t0 ~0.5) is arithmetically
impossible". **That step is invalid and has been refuted by construction.**
Two bins with EQUAL positive rates have a t0-only ceiling of exactly 0.500, yet
a score whose within-bin AUC is exactly 0.5 in BOTH bins reaches pooled 0.625 --
and 4 of 5 brute-forced bin configurations exceed their ceiling at zero within-bin
skill (`_refute_ceiling.py`, exhaustive over integer scorings, ties included).
Variation within a bin is NECESSARY for within-bin discrimination but not
SUFFICIENT: the variation can order CROSS-bin pairs instead.

So a control landing at (pooled ~0.84, within-t0 ~0.5) is NOT a contradiction --
it is the very signature of a pooled AUC carried by t0 ordering, i.e. of the
within-t0 fix doing its job. The valid reading of a positive residual is "t0
alone cannot produce this pooled AUC"; the invalid reading is "therefore its
within-t0 AUC exceeds 0.5".
"""
import json
import sys

import numpy as np
from scipy.stats import rankdata


def closed_form(pb, keys):
    Npos = sum(pb[k][2] for k in keys)
    Nneg = sum(pb[k][0] - pb[k][2] for k in keys)
    strict = ties = 0.0
    for i in keys:
        npi, ri = pb[i][2], pb[i][3]
        for j in keys:
            npj, nnj, rj = pb[j][2], pb[j][0] - pb[j][2], pb[j][3]
            if ri > rj:
                strict += npi * nnj
            elif ri == rj and i == j:
                ties += npi * nnj
    return (strict + 0.5 * ties) / (Npos * Nneg), Npos, Nneg


def by_construction(pb, keys):
    sc, lab = [], []
    for k in keys:
        n, _a, n_pos, rate = pb[k]
        n, n_pos = int(n), int(n_pos)
        sc.append(np.full(n, float(rate)))
        lab.append(np.concatenate([np.ones(n_pos), np.zeros(n - n_pos)]))
    s = np.concatenate(sc)
    y = np.concatenate(lab)
    Np = int(y.sum())
    Nn = len(y) - Np
    r = rankdata(s)
    return (r[y == 1].sum() - Np * (Np + 1) / 2.0) / (Np * Nn), Np, Nn


def main():
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    ctl = {k: float(v) for k, v in d["leakage_check"]
           ["shuffled_label_control"]["test_auc_by_delta"].items()}
    arm = sys.argv[2] if len(sys.argv) > 2 else "tgn"

    print("Delta  ceiling   (closed / rank)      control_pooled   residual")
    worst = 0.0
    for D in sorted(ctl):
        pb = d["arms"][arm]["by_delta"][D]["within_t0_auc"]["per_bin"]
        keys = sorted(pb, key=lambda x: int(x))
        a, npa, nna = closed_form(pb, keys)
        b, npb_, nnb = by_construction(pb, keys)
        worst = max(worst, abs(a - b))
        assert (npa, nna) == (npb_, nnb), "population mismatch between methods"
        c = ctl[D]
        print("  %s   %.4f / %.4f  %s   %.6f   %+.4f"
              % (D, a, b, "OK  " if abs(a - b) < 1e-9 else "DIFF", c, c - b))
    print()
    print("max |closed - rank| = %.2e (they must agree exactly)" % worst)
    print("residual = control_pooled - ceiling. POSITIVE means t0 ALONE cannot")
    print("produce this pooled AUC: the scores vary WITHIN bins. It does NOT")
    print("imply the within-t0 AUC exceeds 0.5 -- that variation can order")
    print("CROSS-bin pairs instead (C-172; see _refute_ceiling.py).")


if __name__ == "__main__":
    main()
