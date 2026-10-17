# -*- coding: utf-8 -*-
"""Diff the closed form against the rank construction on one Delta, term by term.

Two implementations of the same ceiling disagreed by 0.06. Disagreement means at
least one is wrong, so rather than keep the one that happened to match the peer,
locate the term that differs.
"""
import json
import sys

import numpy as np
from scipy.stats import rankdata

d = json.load(open(sys.argv[1], encoding="utf-8"))
D = "5"
pb = d["arms"]["tgn"]["by_delta"][D]["within_t0_auc"]["per_bin"]
ctl = float(d["leakage_check"]["shuffled_label_control"]["test_auc_by_delta"][D])

keys = sorted(pb, key=lambda x: int(x))
Np = sum(pb[k][2] for k in keys)
Nn = sum(pb[k][0] - pb[k][2] for k in keys)
print("Np=%d Nn=%d  control=%.6f" % (Np, Nn, ctl))

# --- closed form, as written in _ceiling_check.py -------------------------
strict = 0.0
ties = 0.0
for i in keys:
    ni, npi, ri = pb[i][0], pb[i][2], pb[i][3]
    for j in keys:
        nj, npj, rj = pb[j][0], pb[j][2], pb[j][3]
        if ri > rj:
            strict += npi * (nj - npj)
        elif ri == rj and i == j:
            ties += npi * (nj - npj)
closed = (strict + 0.5 * ties) / (Np * Nn)

# --- the identity it should satisfy ---------------------------------------
# For ordered pairs i != j, exactly one of r_i > r_j, r_i < r_j holds.
# So strict + reverse + ties(i==j) must equal Np*Nn.
reverse = 0.0
for i in keys:
    for j in keys:
        if pb[i][3] < pb[j][3]:
            reverse += pb[i][2] * (pb[j][0] - pb[j][2])
print("strict=%.1f reverse=%.1f ties=%.1f  sum=%.1f  Np*Nn=%.1f"
      % (strict, reverse, ties, strict + reverse + ties, Np * Nn))
print("closed form ceiling = %.6f" % closed)

# --- rank construction ----------------------------------------------------
scores, labels = [], []
for k in keys:
    n, _a, n_pos, rate = pb[k]
    n, n_pos = int(n), int(n_pos)
    scores.append(np.full(n, float(rate)))
    labels.append(np.concatenate([np.ones(n_pos), np.zeros(n - n_pos)]))
s = np.concatenate(scores)
y = np.concatenate(labels)
r = rankdata(s)
rank_auc = (r[y == 1].sum() - Np * (Np + 1) / 2.0) / (Np * Nn)
print("rank construction ceiling = %.6f" % rank_auc)
print()
print("difference = %+.6f" % (closed - rank_auc))
