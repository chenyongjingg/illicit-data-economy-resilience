# -*- coding: utf-8 -*-
"""Is `pooled > t0-only ceiling` enough to force within-bin skill?

THE CLAIM UNDER TEST (mine, pre-registered in report 16_ and in C-170 §4):
    if a run shows the control's within-t0 ~ 0.5 AND pooled ~ 0.84, that pair is
    "arithmetically impossible", so it would be a writer defect, not a result.

The ceiling is the maximum pooled AUC over scores that are a function of t0 ONLY,
i.e. constant within each bin with the bins ordered by positive rate. My
inference was: pooled above that ceiling => the score must discriminate WITHIN
bins. That inference holds only if a score with within-bin AUC = 0.5 everywhere
*cannot* beat the ceiling.

So: brute-force it. Two bins, small counts, every assignment of integer scores
from a small level set (TIES ALLOWED -- `auc` is `roc_auc_score`, which credits a
tied pair 0.5, and ties are exactly how a constant-within-bin score reaches 0.5).
Keep the assignments whose within-bin AUC is exactly 0.5 in BOTH bins, and report
the maximum pooled AUC among them.

  max > ceiling  =>  the claim is dead
  max == ceiling =>  the claim survives as an inequality (at this resolution)

**SUPERSEDED FOR THE SUPREMUM (C-180).** `_sup_weakorder.py` now computes the
EXACT constrained supremum by enumerating weak orderings and asserting its leaf
count against Fubini(n). For every configuration small enough to run, its value
equals the maximum printed here -- so this file's numbers were right and remain
useful as an independent cross-check. But "max over the L=n grid" is the correct
justification for calling them suprema, not a plateau in L, and that justification
lives in the other tool. Prefer `_sup_weakorder.py` when citing a supremum.

**WHAT A SEARCH REPORTS, AND WHAT IT DOES NOT (C-177).**
The first version of this file printed a single number per configuration under the
heading "max pooled at within-AUC = 0.5". That heading asserts a MAXIMUM; the
number is the max over the level set that was searched. They are not the same
statement, and here the gap is measurable: for (2,2,2,2) the value is
0.5625 / 0.625 / 0.65625 at L = 3 / 4 / 5. It is still rising at L = 5, so the
true supremum is unknown and 0.625 is a WITNESSED LOWER BOUND.

The peer caught exactly this in my (3,1,1,3) row -- "未超" is a negative
existential over a grid, not a proof of impossibility -- and it applies to the
headline row too, and (symmetrically) to the peer's own "independent of bin size"
remark: (1,1,3,3) plateaus at 0.5625 for L = 4 and 5 while (2,2,2,2) keeps rising,
so the achievable max is NOT size-independent even though the identity below is.
L=6 settles the direction and adds the contrast that matters (C-177 section 6):
(1,1,3,3) is FLAT at 0.5625 across L=4/5/6 while (2,2,2,2) RISES to 0.6875, both
at equal rates. So L-dependence is ITSELF configuration-dependent, and "the grid
limits it" is no safer than "this is the max" -- the witnessed bound is per
(configuration, L), not per configuration.

Nothing about the conclusion changes, because ONE witness suffices and a witness
at L = 4 is a witness. `levels` is therefore swept and printed rather than fixed
at 4, and the equal-rate case gets the analytic bound it deserves:

    FOR TWO BINS WITH THE SAME POSITIVE RATE, pooled = (1 + P12 + P21)/4

where P12 = P(pos in bin1 ranks above neg in bin2), P21 the reverse. The ceiling
for that configuration is exactly 0.500, and P12 + P21 = 1.5 gives 0.625. The
identity is analytic and size-independent; the constrained MAXIMUM is not.
"""
import itertools
import sys


def auc(pos, neg):
    """roc_auc_score's convention: P(pos>neg) + 0.5*P(pos==neg)."""
    if not pos or not neg:
        return None
    c = 0.0
    for p in pos:
        for n in neg:
            c += 1.0 if p > n else (0.5 if p == n else 0.0)
    return c / (len(pos) * len(neg))


def study(p1, q1, p2, q2, levels):
    items = [("p", 1)] * p1 + [("n", 1)] * q1 + [("p", 2)] * p2 + [("n", 2)] * q2
    best, n_ok = None, 0
    for assign in itertools.product(range(levels), repeat=len(items)):
        idx = {}
        for i, it in enumerate(items):
            idx.setdefault(it, []).append(assign[i])
        if auc(idx.get(("p", 1), []), idx.get(("n", 1), [])) != 0.5:
            continue
        if auc(idx.get(("p", 2), []), idx.get(("n", 2), [])) != 0.5:
            continue
        n_ok += 1
        pooled = auc(idx.get(("p", 1), []) + idx.get(("p", 2), []),
                     idx.get(("n", 1), []) + idx.get(("n", 2), []))
        if best is None or pooled > best:
            best = pooled
    return best, n_ok


def ceiling(p1, q1, p2, q2):
    r1, r2 = p1 / (p1 + q1), p2 / (p2 + q2)
    if r1 >= r2:
        hp, _hn, lp, ln = p1, q1, p2, q2
    else:
        hp, _hn, lp, ln = p2, q2, p1, q1
    return (0.5 * (p1 * q1 + p2 * q2) + hp * ln) / ((p1 + p2) * (q1 + q2))


print("Can a score with ZERO within-bin skill (within-AUC = 0.5 in every bin)")
print("still beat the t0-only ceiling?  Ties allowed (roc_auc_score convention).")
print()
print("A witness at any level set refutes the claim; the printed value is the max")
print("over THAT level set, so it is a LOWER BOUND on the supremum (C-177).\n")

cases = [(2, 2, 1, 3), (2, 2, 2, 2), (3, 1, 1, 3), (2, 3, 1, 4), (1, 2, 1, 3)]
LEVELS = (3, 4, 5, 6)

# THE BUDGET GUARD'S QUANTITY, STATED CORRECTLY (C-179). It read `n_total ** L`,
# which is the number of ITEMS to the level count -- but
# `itertools.product(range(levels), repeat=len(items))` enumerates
# `levels ** n_total` tuples. The exponents were SWAPPED. The guard therefore
# admitted every cell up to 4e6 while the (2,3,1,4) cell at L=6 actually costs
# 6**10 = 60,466,176 -- a 60x overshoot, and the tool ran for minutes with no
# output. A guard whose predicate is not the quantity it is guarding is the same
# defect as a label that is not the predicate it prints; here it failed OPEN,
# which is the direction that costs wall-clock rather than correctness.
BUDGET = 3_000_000
skipped = []
print("%-18s %9s" % ("bins(p,q,p,q)", "ceiling")
      + "".join("%10s" % ("L=%d" % L) for L in LEVELS) + "   verdict")
beat = 0
for c in cases:
    ceil = ceiling(*c)
    vals = []
    for L in LEVELS:
        n_total = sum(c)
        cost = L ** n_total          # product(range(L), repeat=n_total)
        if cost > BUDGET:
            vals.append(None)
            skipped.append((c, L, cost))
            continue
        b, _ = study(*c, levels=L)
        vals.append(b)
    cells = " ".join("%10s" % ("%.6f" % v if v is not None else "skip")
                     for v in vals)
    # verdict on the SMALLEST level set that produced a value: the weakest
    # assumption needed is the one that matters.
    first = next((v for v in vals if v is not None), None)
    if first is None:
        verdict = "n/a"
    elif first > ceil + 1e-12:
        verdict = "**EXCEEDS ceiling**"
        beat += 1
    else:
        verdict = "not found at this resolution"
    print("%-18s %9.6f %s   %s" % (str(c), ceil, cells, verdict))

print()
if skipped:
    print("NOT SEARCHED (budget %d tuples; a `skip` cell is a statement about this" % BUDGET)
    print("program's budget, NOT a negative result about the mathematics):")
    for c, L, cost in skipped:
        print("   bins=%s L=%d costs %s**%d = %d tuples"
              % (str(c), L, L, sum(c), cost))
    print()
print("%d case(s) in which zero within-bin skill BEATS the ceiling." % beat)
print()
print("Equal-rate bins, analytically: pooled = (1 + P12 + P21)/4, and the ceiling")
print("for that configuration is exactly 0.500. P12+P21 = 1.5 (e.g. the peer's")
print("witness neg1=pos1={10,10}, neg2={0,0}, pos2={-1,20}) gives 0.625.")
print()
if beat:
    print("=> `pooled > ceiling` does NOT imply within-bin skill.")
    print("=> my 'arithmetically impossible' claim is REFUTED.")
    print("=> the pre-registered defect oracle is WITHDRAWN, not kept.")
else:
    print("=> `pooled > ceiling` implies within-bin skill in these cases.")
