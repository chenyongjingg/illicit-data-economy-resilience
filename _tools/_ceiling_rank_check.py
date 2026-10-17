# -*- coding: utf-8 -*-
"""Independent computation of the within-bin-constant ceiling, by construction.

The closed form sums pairwise counts. This builds the actual population implied
by per_bin -- n addresses per bin, each scored with its bin's positive rate --
and computes AUC the Mann-Whitney way from ranks. Same quantity, different
implementation, so agreement is evidence and disagreement localises the error.

Also checks the premise that all three arms share one test population, and that
the recorded per_bin entry is [n, within_t0_auc, n_pos, pos_rate].
"""
import json
import sys

import numpy as np
from scipy.stats import rankdata

d = json.load(open(sys.argv[1], encoding="utf-8"))
ctl = {k: float(v) for k, v in
       d["leakage_check"]["shuffled_label_control"]["test_auc_by_delta"].items()}

print("== premise: do the three arms share one per-bin population? ==")
for D in sorted(ctl):
    sig = {}
    for a in ("mlp_feature_only", "graphsage", "tgn"):
        pb = d["arms"][a]["by_delta"][D]["within_t0_auc"]["per_bin"]
        sig[a] = tuple((pb[k][0], pb[k][2]) for k in sorted(pb, key=int))
    same = len(set(sig.values())) == 1
    print("  Delta=%s  identical (n, n_pos) across arms: %s   bins=%d"
          % (D, same, len(sig["tgn"])))
    if not same:
        for a in sig:
            print("     %s: %s" % (a, sig[a][:3]))

print()
print("== ceiling by construction (rank-based), using TGN's per_bin ==")
print("Delta  n_total  n_pos  ceiling   control_pooled   residual")
for D in sorted(ctl):
    pb = d["arms"]["tgn"]["by_delta"][D]["within_t0_auc"]["per_bin"]
    scores, labels = [], []
    for k in sorted(pb, key=int):
        n, _auc, n_pos, rate = pb[k]
        n, n_pos = int(n), int(n_pos)
        scores.append(np.full(n, float(rate)))
        labels.append(np.concatenate([np.ones(n_pos), np.zeros(n - n_pos)]))
    s = np.concatenate(scores)
    y = np.concatenate(labels)
    N, Np = len(s), int(y.sum())
    Nn = N - Np
    r = rankdata(s)                      # average ranks for ties
    auc = (r[y == 1].sum() - Np * (Np + 1) / 2.0) / (Np * Nn)
    c = ctl[D]
    print("  %s   %7d %6d   %.4f   %.6f      %+.4f"
          % (D, N, Np, auc, c, c - auc))
print()
print("residual = control_pooled - ceiling.")
