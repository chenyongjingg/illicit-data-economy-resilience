# -*- coding: utf-8 -*-
"""EXACT constrained supremum, by enumerating WEAK ORDERINGS.

WHY A GRID SWEEP CAN BE REPLACED (the peer's covering argument, verified).
`auc` is a function of pairwise `>` / `==` / `<` relations alone. Replacing every
value by its rank among the distinct values present preserves all pairwise
relations, hence preserves both within-bin AUCs, the `within-AUC == 0.5`
constraint, and the pooled AUC. Any real assignment therefore collapses into one
using at most n distinct values, i.e. into the L=n grid. Hence

    max over the L=n integer grid  ==  sup over ALL real scores.

WHY THE FIRST VERSION OF THIS FILE WAS WRONG, AND HOW IT SHOWED ITSELF.
It used a restricted-growth recursion: `a[0] = 0`, `a[i] <= 1 + max(a[..i-1])`.
That enumerates SET PARTITIONS (Bell(n)), not ordered ones -- it pins item 0 into
the lowest class, so only the orderings in which item 0 is minimal are reached.
It therefore enumerated Fubini(n-1) patterns while PRINTING `Fubini(n)` as the
count it was about to search.

What exposed it was not a re-reading: the computed "exact sup" came out BELOW a
grid value already measured for the same configuration, which is impossible for
an enumeration that contains the grid. E.g. (2,2,2,2) returned 0.593750 when the
grid already gave 0.687500. A claimed over-set producing a smaller maximum is
self-refuting, so the number never had to be trusted.

THE FIX. Enumerate set partitions by restricted growth (Bell(n) = 4140 at n=8),
then for each partition try EVERY ordering of its k blocks. The leaf count is
sum_k k! * S(n,k) = Fubini(n) = 545,835 at n=8, and the tool now ASSERTS the
leaf count it actually reached against that formula before reporting anything.

n=10 is Fubini(10) = 102,247,563 and is honestly reported as out of budget.
"""
import itertools
import sys
import time
from math import comb, factorial

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def auc(p, n):
    if not p or not n:
        return None
    c = 0.0
    for a in p:
        for b in n:
            c += 1.0 if a > b else (0.5 if a == b else 0.0)
    return c / (len(p) * len(n))


def fubini(n):
    F = [1]
    for m in range(1, n + 1):
        F.append(sum(comb(m, j) * F[m - j] for j in range(1, m + 1)))
    return F[n]


def sup_weakorder(p1, q1, p2, q2, budget=20_000_000):
    items = [("p", 1)] * p1 + [("n", 1)] * q1 + [("p", 2)] * p2 + [("n", 2)] * q2
    n = len(items)
    need = fubini(n)
    if need > budget:
        return None, need, 0

    P1 = [i for i, it in enumerate(items) if it == ("p", 1)]
    N1 = [i for i, it in enumerate(items) if it == ("n", 1)]
    P2 = [i for i, it in enumerate(items) if it == ("p", 2)]
    N2 = [i for i, it in enumerate(items) if it == ("n", 2)]

    best = [None]
    block = [0] * n
    val = [0] * n
    leaves = [0]

    def evaluate():
        leaves[0] += 1
        g1p = [val[i] for i in P1]
        g1n = [val[i] for i in N1]
        g2p = [val[i] for i in P2]
        g2n = [val[i] for i in N2]
        if auc(g1p, g1n) != 0.5 or auc(g2p, g2n) != 0.5:
            return
        po = auc(g1p + g2p, g1n + g2n)
        if best[0] is None or po > best[0][0]:
            best[0] = (po, list(val))

    def rec(i, k):
        """restricted growth: enumerate SET partitions (blocks unordered)"""
        if i == n:
            # then all k! ORDERINGS of the k blocks -- this is what the first
            # version omitted, and omitting it is what made the max too small
            for perm in itertools.permutations(range(k)):
                for j in range(n):
                    val[j] = perm[block[j]]
                evaluate()
            return
        for c in range(k + 1):
            block[i] = c
            rec(i + 1, k + 1 if c == k else k)
        block[i] = 0

    rec(0, 0)
    return (best[0][0] if best[0] else None), need, leaves[0]


def ceiling(p1, q1, p2, q2):
    r1, r2 = p1 / (p1 + q1), p2 / (p2 + q2)
    if r1 >= r2:
        hp, _hn, lp, ln = p1, q1, p2, q2
    else:
        hp, _hn, lp, ln = p2, q2, p1, q1
    return (0.5 * (p1 * q1 + p2 * q2) + hp * ln) / ((p1 + p2) * (q1 + q2))


# ---------------- self-check: the enumerated leaf count must BE Fubini(n) -----
print("SELF-CHECK (asserted, not claimed): enumerated leaves == Fubini(n)")
ok = True
for c in [(1, 1, 1, 1), (2, 2, 1, 1), (2, 2, 2, 2), (1, 1, 3, 3)]:
    _v, _need, leaves = sup_weakorder(*c)
    good = (leaves == _need)
    ok = ok and good
    print("   bins=%-14s n=%d  leaves=%-9d Fubini(n)=%-9d %s"
          % (str(c), sum(c), leaves, _need, "OK" if good else "**MISMATCH**"))
if not ok:
    print("\nLEAF COUNT DOES NOT MATCH -- the enumeration is not exhaustive. Stopping.")
    sys.exit(3)
print("   => enumeration is exhaustive: it reaches exactly Fubini(n) weak orderings\n")

cases = [(2, 2, 1, 3), (2, 2, 2, 2), (3, 1, 1, 3), (2, 3, 1, 4), (1, 2, 1, 3),
         (1, 1, 3, 3)]
print("EXACT constrained sup over ALL real scores.\n")
print("%-16s %4s %12s %12s %12s   %s"
      % ("bins(p,q,p,q)", "n", "Fubini(n)", "t0-ceiling", "EXACT sup", "verdict"))
beat = exact = 0
for c in cases:
    t0 = time.time()
    val, need, leaves = sup_weakorder(*c)
    ceil = ceiling(*c)
    if val is None:
        verdict, shown = "OUT OF BUDGET (Fubini(n)=%d)" % need, "not computed"
    else:
        assert leaves == need, "leaf count drifted for %s" % (c,)
        exact += 1
        shown = "%.6f" % val
        if val > ceil + 1e-12:
            verdict = "**EXCEEDS ceiling**"
            beat += 1
        else:
            verdict = "does NOT exceed"
    print("%-16s %4d %12d %12.6f %12s   %s  [%.1fs]"
          % (str(c), sum(c), need, ceil, shown, verdict, time.time() - t0))

print()
print("%d of %d computed EXACTLY; %d exceed the ceiling." % (exact, len(cases), beat))
print()
print("(2,3,1,4) is not computed: Fubini(10)=%d. Its sup is NOT claimed, and does" % fubini(10))
print("not need to be -- the peer's witness gives pooled = 2/3 > 0.619048, and one")
print("witness refutes. The refutation never depended on the sup.")
print()
print("=> `pooled > ceiling` does NOT imply within-bin skill, exactly.")
