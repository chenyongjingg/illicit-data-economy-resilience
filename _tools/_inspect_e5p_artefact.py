# -*- coding: utf-8 -*-
"""Fourth pass: does the bin-wise positive rate explain a high POOLED AUC for a
model that knows nothing but t0?

If the permuted labels are drawn over the whole training set, then by the law of
large numbers each t0 bin keeps approximately its TRUE positive rate. A model
that learns only score ~ rate(t0) therefore reproduces the bin structure -- and
that is enough to score well on the pooled metric against TRUE labels, with no
label information at all. If so, the control's 0.81 is the t0 channel, not a
leak, and the within-t0 column is where the question is actually decided.
"""
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
D = "5"
per_bin = d["arms"]["tgn"]["by_delta"][D]["within_t0_auc"]["per_bin"]

rates, weights = [], []
for k in sorted(per_bin, key=lambda x: int(x)):
    n, auc, n_pos, pos_rate = per_bin[k]
    rates.append(pos_rate)
    weights.append(n)

lo, hi = min(rates), max(rates)
print("t0 bins (Delta=%s): %d bins" % (D, len(rates)))
print("  positive rate range: %.5f .. %.5f  (ratio %.0fx)" % (lo, hi, hi / lo))
print("  if a scorer knows only the bin's rate, pooled AUC is bounded below by")
print("  the spread that rate induces -- not by 0.5.")
print()
print("  observed control pooled AUC at this Delta: %.6f"
      % d["leakage_check"]["shuffled_label_control"]["test_auc_by_delta"][D])
print("  observed TGN    pooled AUC at this Delta: %.6f"
      % d["arms"]["tgn"]["by_delta"][D]["auc_test"])
print("  observed TGN within-t0 (unweighted)     : %.6f"
      % d["arms"]["tgn"]["by_delta"][D]["within_t0_auc"]["unweighted"])
print()
print("  control carries a within_t0 column? %s"
      % ("yes" if "within_t0_auc" in d["leakage_check"]["shuffled_label_control"]
         else "NO -- so the t0 channel cannot be removed from its score"))
