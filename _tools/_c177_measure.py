# -*- coding: utf-8 -*-
"""Two measurements the C-177 addendum must not assert without making.

(A) THE PEER'S SHARPENING: for equal-rate bins, sup = max over t = q2/q1 of
    [0.5(1+t^2) + 2t]/(1+t)^2, claimed to be exactly 0.75 AT t=1 (equal sizes)
    and strictly less otherwise. If true, the 0.75 bound is attained only on
    the equal-size family -- so it is a bound on the CONFIGURATION, not on the
    grid. Verify numerically, including that t=1 is a maximum rather than just
    a value.

(B) MY OWN §2 CLAIM, WHICH HAS THE SAME DEFECT I AM CORRECTING. I wrote that
    (1,1,3,3)'s plateau "is the GRID limiting that configuration -- a reason,
    not just a not-found". I know only that the observed 0.5625 pins the
    achievable P12+P21 at 4/3 against a theoretical 2. WHETHER A FINER GRID
    WOULD CLOSE THAT GAP IS UNTESTED BY ME. So: test it. (1,1,3,3) is 8 items,
    so L=6 is 262,144 assignments and L=7 is 2.1M -- both affordable.
    If it moves, my "the grid limits it" was wrong; if it holds across L, the
    plateau is structural and the claim survives as a measurement.
"""
import itertools
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


print("=== (A) the equal-rate sup as a function of the size ratio t = q2/q1 ===")
print("(peer: sup is 0.75 attained ONLY at t=1; equal-size family is the equality case)")
worst = None
for t in (1, 2, 3, 5, 10, 100):
    v = (0.5 * (1 + t * t) + 2 * t) / (1 + t) ** 2
    print("   t=%-4s  sup=%.9f" % (t, v))
    if worst is None or v > worst[1]:
        worst = (t, v)
print("   max over these t: t=%s -> %.9f" % worst)
# is t=1 a genuine interior max? sample densely and also probe below 1
best = max(((t / 100.0, (0.5 * (1 + (t / 100.0) ** 2) + 2 * (t / 100.0))
             / (1 + t / 100.0) ** 2) for t in range(1, 1001)), key=lambda x: x[1])
print("   dense sweep t in (0,10]: max at t=%.2f -> %.9f" % best)
print("   => 0.75 is attained at t=1 and nowhere else: %s"
      % ("CONFIRMED" if abs(best[0] - 1.0) < 0.02 and abs(best[1] - 0.75) < 1e-9 else "NOT confirmed"))


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


print()
print("=== (B) does the (1,1,3,3) plateau move under a finer grid? ===")
print("    identity there: pooled = [5 + 3*(P12+P21)]/16")
print("%-16s %10s %10s   %s" % ("config", "L", "max", "implied P12+P21"))
for c in [(1, 1, 3, 3), (2, 2, 2, 2)]:
    for L in (4, 5, 6):
        b, n = study(*c, levels=L)
        if b is None:
            print("%-16s %10d   none" % (str(c), L))
            continue
        implied = (16 * b - 5) / 3 if c == (1, 1, 3, 3) else None
        print("%-16s %10d %10.6f   %s" % (str(c), L, b,
              ("%.6f / 2.0" % implied) if implied is not None else ""))
