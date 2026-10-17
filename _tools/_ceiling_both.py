# -*- coding: utf-8 -*-
"""Both ceiling computations in ONE process, same pb object, all Deltas.

Two scripts with identical-looking formulas returned 0.8170 and 0.7723 for the
same input. Running both against the same in-memory object removes every
difference except the arithmetic itself.
"""
import json
import sys

import numpy as np
from scipy.stats import rankdata

d = json.load(open(sys.argv[1], encoding="utf-8"))
ctl = {k: float(v) for k, v in
       d["leakage_check"]["shuffled_label_control"]["test_auc_by_delta"].items()}

for D in sorted(ctl):
    pb = d["arms"]["tgn"]["by_delta"][D]["within_t0_auc"]["per_bin"]
    keys = sorted(pb, key=lambda x: int(x))

    # (A) closed form, exactly as _ceiling_check.py writes it
    cells = [(pb[k][0] - pb[k][2], pb[k][2]) for k in keys]
    tot = sum(n for n, _ in cells)
    NposA = sum(p for _, p in cells)
    NnegA = tot - NposA
    strictA = tiesA = 0.0
    for i in keys:
        ni, npi, ri = pb[i][0], pb[i][2], pb[i][3]
        for j in keys:
            nj, npj, rj = pb[j][0], pb[j][2], pb[j][3]
            if ri > rj:
                strictA += npi * (nj - npj)
            elif ri == rj and i == j:
                tiesA += npi * (nj - npj)
    ceilA = (strictA + 0.5 * tiesA) / (NposA * NnegA)
    print("   [A] strict=%.0f ties=%.0f Npos=%d Nneg=%d  strict+ties=%.0f "
          "Npos*Nneg=%.0f" % (strictA, tiesA, NposA, NnegA,
                              strictA + tiesA, NposA * NnegA))

    # (B) rank construction
    sc, lab = [], []
    for k in keys:
        n, _a, n_pos, rate = pb[k]
        n, n_pos = int(n), int(n_pos)
        sc.append(np.full(n, float(rate)))
        lab.append(np.concatenate([np.ones(n_pos), np.zeros(n - n_pos)]))
    s = np.concatenate(sc)
    y = np.concatenate(lab)
    Np, Nn = int(y.sum()), len(y) - int(y.sum())
    r = rankdata(s)
    ceilB = (r[y == 1].sum() - Np * (Np + 1) / 2.0) / (Np * Nn)

    print("Delta=%s  closed=%.6f  rank=%.6f  diff=%+.6f  ctl=%.6f"
          % (D, ceilA, ceilB, ceilA - ceilB, ctl[D]))
