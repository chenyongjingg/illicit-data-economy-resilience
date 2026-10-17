# -*- coding: utf-8 -*-
"""Verify the peer's three checkable claims at source, rather than transcribing.

CLAIM 3 (about MY output): "Your row (2,3,1,4) prints 0.642857 under an L=4
heading. 0.642857 is EXACTLY my L=3 value; the true L=4 max is 0.666667."
Settle it by running my own study() on that config at L=3 and L=4 and comparing,
and by checking the peer's own witness by hand.

THE PEER'S WITNESS: pos1=[2,2], neg1=[3,2,0], pos2=[1], neg2=[1,1,1,1],
claimed within-AUC = (0.5, 0.5) and pooled = 14/21 = 2/3.

CLAIM 1 (the covering argument): `auc` is a function of pairwise comparisons and
ties only, so an order-preserving relabelling preserves every AUC; a pattern on n
items therefore uses at most n distinct values and is already realised inside
{0..n-1}. Tested here by brute force on a small config: max over a dense real
grid vs max over the weak orderings induced by it.
"""
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def auc(p, n):
    if not p or not n:
        return None
    c = 0.0
    for a in p:
        for b in n:
            c += 1.0 if a > b else (0.5 if a == b else 0.0)
    return c / (len(p) * len(n))


def score(items, assign):
    """items: list of (kind, bin). assign: list of values. Returns (a1, a2, pooled)."""
    g = {}
    for it, v in zip(items, assign):
        g.setdefault(it, []).append(v)
    a1 = auc(g.get(("p", 1), []), g.get(("n", 1), []))
    a2 = auc(g.get(("p", 2), []), g.get(("n", 2), []))
    po = auc(g.get(("p", 1), []) + g.get(("p", 2), []),
             g.get(("n", 1), []) + g.get(("n", 2), []))
    return a1, a2, po


print("=== CLAIM 3: my own (2,3,1,4) cells at L=3 and L=4 ===")
import itertools
c = (2, 3, 1, 4)
items = [("p", 1)] * c[0] + [("n", 1)] * c[1] + [("p", 2)] * c[2] + [("n", 2)] * c[3]
for L in (3, 4):
    best, n_ok, wit = None, 0, None
    for assign in itertools.product(range(L), repeat=len(items)):
        a1, a2, po = score(items, assign)
        if a1 != 0.5 or a2 != 0.5:
            continue
        n_ok += 1
        if best is None or po > best:
            best, wit = po, assign
    print("  L=%d  max=%.6f  (=%.6f as a fraction-free value)  legal=%d  witness=%s"
          % (L, best, best, n_ok, wit))

print()
print("=== the peer's own witness, scored by MY auc() ===")
# pos1 = 2,2 ; neg1 = 3,2,0 ; pos2 = 1 ; neg2 = 1,1,1,1
w_assign = [2, 2, 3, 2, 0, 1, 1, 1, 1, 1]
w_items = [("p", 1), ("p", 1), ("n", 1), ("n", 1), ("n", 1),
           ("p", 2), ("n", 2), ("n", 2), ("n", 2), ("n", 2)]
a1, a2, po = score(w_items, w_assign)
print("  item order used: pos1=[2,2], neg1=[3,2,0], pos2=[1], neg2=[1,1,1,1]")
print("  within-AUC bin1 = %.6f   bin2 = %.6f   pooled = %.6f  (14/21 = %.6f)"
      % (a1, a2, po, 14 / 21))
print("  => peer's witness is %s"
      % ("VALID" if abs(a1 - 0.5) < 1e-12 and abs(a2 - 0.5) < 1e-12
         and abs(po - 14 / 21) < 1e-12 else "NOT reproducible"))
print("  NOTE: it uses values {0,1,2,3}, so it requires L>=4 -- which is the")
print("  whole point: it cannot be found at L=3.")

print()
print("=== CLAIM 1: is max over {0..n-1} the sup over all reals? ===")
print("REPLACED 2026-09-24 (C-182). The previous test sampled 400k random real")
print("assignments and checked best_real <= best_int. THAT TEST CAN NEVER FAIL:")
print("any real assignment has an ORDER TYPE, and every order type on n items is")
print("realised by some integer assignment in {0..n-1}, so the sampler's space is")
print("a subset of the grid's and the inequality holds by construction. A test that")
print("cannot fail is not evidence for the claim it is attached to.")
print()
print("What the covering argument actually asserts is: THE SCORE DEPENDS ONLY ON")
print("THE ORDER TYPE. That is testable, and it has two halves -- an invariance and")
print("its positive control. An invariance with no sensitivity control is itself")
print("unfalsifiable, because a scorer that returned a constant would pass it.")
small = (2, 2, 1, 1)   # 6 items
s_items = [("p", 1)] * 2 + [("n", 1)] * 2 + [("p", 2)] * 1 + [("n", 2)] * 1
n_items = len(s_items)


def best_on_grid(items, L):
    """max pooled with within-AUC exactly 0.5 in both bins, over {0..L-1}^n."""
    best, wit = None, None
    for a in itertools.product(range(L), repeat=len(items)):
        r1, r2, po = score(items, a)
        if r1 == 0.5 and r2 == 0.5 and (best is None or po > best):
            best, wit = po, a
    return best, wit


print()
print("  1a. weak orders enumerated DIRECTLY, independent of the integer grid")
print("      A restricted growth string enumerates one SET PARTITION of the item")
print("      POSITIONS. But an order type also needs an ORDER on the blocks, and")
print("      the labels-as-values convenience pins the block holding position 0 as")
print("      the lowest -- which realises exactly ONE of the k! block orderings.")
print("      My first version of this test did that, and reported 0.5 against the")
print("      grid's 0.6111. THE ENUMERATION was incomplete, not the claim. The")
print("      correct count is Fubini(n) = sum_k k! * S(n,k) = 4683 at n=6, and it")
print("      is self-certified below rather than trusted.")


def stirling2(n, k):
    """S(n,k) by the standard recurrence -- computed, not quoted."""
    if n == 0:
        return 1 if k == 0 else 0
    if k == 0 or k > n:
        return 0
    return k * stirling2(n - 1, k) + stirling2(n - 1, k - 1)


fubini6 = sum(__import__("math").factorial(k) * stirling2(6, k) for k in range(1, 7))
print("      Fubini(6) = sum k!*S(6,k) = %d (expected 4683)" % fubini6)


def weak_orders(n):
    """Every weak order on n labelled positions: partition, then all k! block orders."""
    for rgs in itertools.product(*[range(i + 1) for i in range(n)]):
        if any(rgs[j] > max(rgs[:j] or [0]) + 1 for j in range(n)):
            continue
        k = max(rgs) + 1
        for perm in itertools.permutations(range(k)):
            yield tuple(perm[v] for v in rgs)


best_wo, wit_wo, n_leaves = None, None, 0
for a in weak_orders(n_items):
    n_leaves += 1
    r1, r2, po = score(s_items, a)
    if r1 == 0.5 and r2 == 0.5 and (best_wo is None or po > best_wo):
        best_wo, wit_wo = po, a
print("      leaves actually enumerated: %d  %s"
      % (n_leaves, "== Fubini(6)" if n_leaves == fubini6 else "!= Fubini(6) -- BUG"))
best_int, wit_int = best_on_grid(s_items, n_items)
print("      max over weak orders      : %s" % best_wo)
print("      max over grid {0..n-1}^n  : %s" % best_int)
print("      => %s" % ("EQUAL -- the grid realises every order type, which is the "
                    "covering argument"
                    if n_leaves == fubini6 and best_wo is not None
                    and best_int is not None and abs(best_wo - best_int) < 1e-12
                    else "NOT EQUAL -- investigate"))

print()
print("  1b. INVARIANCE: strictly increasing relabellings must not move the triple")
inv_ok = True
for name, f in (("x -> 2x+1", lambda x: 2 * x + 1),
                ("x -> 3x+7", lambda x: 3 * x + 7),
                ("x -> x*x",   lambda x: x * x)):     # increasing on non-negatives
    moved = score(s_items, [f(v) for v in wit_int])
    same = moved == score(s_items, wit_int)
    inv_ok &= same
    print("      %-12s -> %s  %s" % (name, moved, "IDENTICAL" if same else "MOVED"))
print("      => %s" % ("order-preserving relabelling is a no-op, as claimed"
                    if inv_ok else "INVARIANCE VIOLATED"))

print()
print("  1c. POSITIVE CONTROL: order-CHANGING relabellings MUST move the triple.")
print("      Without this, 1b would also pass on a scorer that ignored its input.")
ctl_ok = True
for name, f in (("x -> -x (reverses)", lambda x: -x),
                ("x -> -2x (reverses)", lambda x: -2 * x)):
    moved = score(s_items, [f(v) for v in wit_int])
    changed = moved != score(s_items, wit_int)
    ctl_ok &= changed
    print("      %-20s -> %s  %s" % (name, moved,
                                     "MOVED (good)" if changed else "UNMOVED (bad)"))
print("      => %s" % ("the scorer IS sensitive to order, so 1b is not vacuous"
                    if ctl_ok else "SCORER IGNORES ORDER -- 1b is vacuous, fix it"))
print()
print("  VERDICT CLAIM 1: %s"
      % ("supported -- invariance holds AND a control shows the scorer could have "
         "failed it" if (inv_ok and ctl_ok) else "NOT SUPPORTED -- see above"))
