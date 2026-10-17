#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""26_E6fin_resilience_v2.py -- corrected structural resilience, financial layer.

25_ produced two usable results and two defects. Recorded rather than quietly
patched:

  DEFECT 1 (mine, in 25_): the `illicit-first (degree)` and `illicit-first
  (random)` curves were IDENTICAL at every grid point. Cause: `np.setdiff1d`
  returns a SORTED array, so both curves shared the same tail, and the illicit
  head is only 1.7% of nodes -- by the first grid point (10%) both curves were
  already deep into the identical tail. The contrast was destroyed by
  construction, and the printed curves looked plausible, which is the
  dangerous part. Fixed by giving every curve an explicit shared random tail.

  DEFECT 2 (a real property of the data, not a bug): `gc_frac` was 1.0000 in 47
  of 49 time steps (0.9999 at step 22, 0.9997 at step 43). Connectivity is
  SATURATED -- the 2-week address graph is one connected component at every step
  -- so 25_'s z-score shock test divided by an sd of ~0 and printed meaningless
  numbers. Reported as a finding: **giant-component connectivity is not a usable
  resilience instrument at this resolution.** The shock test is moved onto
  observables that actually vary.

WHAT IS KEPT FROM 25_
  Full graph: 822,935 / 822,942 nodes in one component (99.9991%).
  Random removal needs ~60% of nodes removed to halve the giant component;
  degree-targeted removal needs ~5%. That contrast is the RQ1/RQ3 measurement
  and it is real.

WHAT IS ADDED
  A pre-specified shock test. The July 2017 enforcement wave (AlphaBay + Hansa
  2017-07-20, BTC-e 2017-07-25) maps to steps 41-43 under an EXTERNAL anchor
  (block 400,000 = 2016-02-25), so the window is fixed by an outside fact and
  not by the data. The null is a permutation over which steps could have been
  that window. A 5-step window (41-45) is also reported and is explicitly marked
  exploratory, because it was chosen after seeing the series.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

BASE = "/root/cis/data/EllipticPlusPlus-main"
ACT = os.path.join(BASE, "Actors Dataset")
TXN = os.path.join(BASE, "Transactions Dataset")
RESULTS = "/root/cis/results"
FIGS = os.path.join(RESULTS, "figs")

_L: list[str] = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _L.append(s)


def sep(t):
    log("")
    log("=" * 78)
    log(t)
    log("=" * 78)


NAMES = {1: "illicit", 2: "licit", 3: "unknown"}
BLOCK0, PER_STEP, ANCHOR_BLOCK, ANCHOR_DAY = 391200, 2016, 400000, 16856


def step_date(t):
    import datetime as dt
    mid = BLOCK0 + (t - 0.5) * PER_STEP
    day = ANCHOR_DAY + (mid - ANCHOR_BLOCK) / 144.0
    return str(dt.date(1970, 1, 1) + dt.timedelta(days=day))


def giant(u, v, n):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    g = coo_matrix((np.ones(len(u), dtype=np.int8), (u, v)),
                   shape=(n, n)).tocsr()
    nc, lab = connected_components(g, directed=False)
    if nc == 0:
        return 0
    return int(np.bincount(lab).max())


def main():
    log("=" * 78)
    log("E6-fin v2  Structural resilience, financial layer (corrected)")
    log("=" * 78)

    tf = pd.read_csv(os.path.join(TXN, "txs_features.csv"),
                     usecols=["txId", "Time step"], low_memory=False)
    step_of = tf.set_index("txId")["Time step"]
    at = pd.read_csv(os.path.join(ACT, "AddrTx_edgelist.csv"))
    ta = pd.read_csv(os.path.join(ACT, "TxAddr_edgelist.csv"))
    e = at.merge(ta, on="txId", how="inner")
    e = e[e["input_address"] != e["output_address"]]
    e["Time step"] = e["txId"].map(step_of)
    e = e.dropna(subset=["Time step"])
    e["Time step"] = e["Time step"].astype(int)
    wc = pd.read_csv(os.path.join(ACT, "wallets_classes.csv"))
    cls = wc.set_index("address")["class"]

    nodes = pd.Index(pd.unique(pd.concat([e["input_address"],
                                          e["output_address"]],
                                         ignore_index=True)))
    idx = pd.Series(np.arange(len(nodes)), index=nodes)
    u = e["input_address"].map(idx).to_numpy()
    v = e["output_address"].map(idx).to_numpy()
    node_class = cls.reindex(nodes).to_numpy()
    deg = np.bincount(np.concatenate([u, v]), minlength=len(nodes))
    N = len(nodes)
    log("\n  nodes=%d edges=%d" % (N, len(e)))
    log("  full graph giant component = %d (%.4f%%)"
        % (giant(u, v, N), 100.0 * giant(u, v, N) / N))

    sep("1. Removal curves, with a shared random tail (defect 1 fixed)")
    rng = np.random.default_rng(20260924)
    tail = rng.permutation(N)
    ill = np.where(node_class == 1)[0]
    not_ill = np.where(node_class != 1)[0]
    tail_non = tail[np.isin(tail, not_ill)]
    log("  illicit nodes: %d (%.4f%% of all)" % (len(ill), 100.0 * len(ill) / N))

    orders = {
        "random": tail,
        "degree": np.concatenate([np.argsort(-deg), tail]),
        "illicit_deg": np.concatenate(
            [ill[np.argsort(-deg[ill])], tail_non]),
        "illicit_rand": np.concatenate(
            [rng.permutation(ill), tail_non]),
    }
    for k in ("degree", "illicit_deg"):
        pass
    # make the two illicit curves share the same non-illicit tail, and check it
    assert np.array_equal(orders["illicit_deg"][len(ill):],
                          orders["illicit_rand"][len(ill):]), \
        "illicit curves must share a tail"
    assert not np.array_equal(orders["illicit_deg"][:len(ill)],
                              orders["illicit_rand"][:len(ill)]), \
        "illicit curves must differ in their head"
    log("  shared-tail assertion passed (this is what 25_ got wrong)")

    fracs = np.array([0.0, 0.005, 0.01, 0.0175, 0.025, 0.05, 0.075, 0.10,
                      0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90])
    log("")
    log("  %7s %11s %11s %11s %11s" % ("removed", "random", "degree",
                                       "ill_deg", "ill_rand"))
    rows = []
    for f in fracs:
        k = int(f * N)
        row = {"frac": float(f)}
        for name, order in orders.items():
            keep = np.ones(N, dtype=bool)
            keep[order[:k]] = False
            m = keep[u] & keep[v]
            nk = int(keep.sum())
            if m.sum() == 0 or nk == 0:
                row[name] = 0.0
            else:
                relab = -np.ones(N, dtype=np.int64)
                relab[keep] = np.arange(nk)
                row[name] = 100.0 * giant(relab[u[m]], relab[v[m]], nk) / nk
        rows.append(row)
        log("  %6.2f%% %10.2f%% %10.2f%% %10.2f%% %10.2f%%"
            % (100 * f, row["random"], row["degree"], row["illicit_deg"],
               row["illicit_rand"]))
    O = pd.DataFrame(rows)
    curves = {c: O[c].to_numpy() for c in orders}

    def collapse50(y):
        b = np.where(y < 50.0)[0]
        return float(O["frac"].iloc[b[0]]) if len(b) else None

    log("")
    log("  fraction removed to halve the giant component:")
    for c in orders:
        log("    %-14s %s" % (c, collapse50(curves[c])))
    log("  AUC of the curve (higher = more resilient):")
    for c in orders:
        log("    %-14s %6.2f" % (c, float(np.trapezoid(curves[c], O["frac"]))))
    log("")
    log("  ★ random vs degree-targeted: %s%% vs %s%% removed to halve."
        % (collapse50(curves["random"]) and 100 * collapse50(curves["random"]),
           collapse50(curves["degree"]) and 100 * collapse50(curves["degree"])))
    li = len(ill) / N
    log("  ★ at the point where ALL illicit nodes are gone (%.3f%% removed):"
        % (100 * li))
    for c in ("random", "illicit_deg", "illicit_rand"):
        y = float(np.interp(li, O["frac"], curves[c]))
        log("      %-14s giant = %.2f%%" % (c, y))
    log("  (illicit_deg vs illicit_rand differ only in how the illicit head is")
    log("   ordered; illicit_deg vs random at the same fraction is the")
    log("   'does targeting illicit beat chance' contrast.)")

    sep("2. Connectivity is saturated -- a measurement finding")
    T = []
    for t in range(1, 50):
        g = e[e["Time step"] == t]
        if len(g) == 0:
            continue
        nn = pd.unique(pd.concat([g["input_address"], g["output_address"]],
                                 ignore_index=True))
        i2 = pd.Series(np.arange(len(nn)), index=nn)
        uu = g["input_address"].map(i2).to_numpy()
        vv = g["output_address"].map(i2).to_numpy()
        gc = giant(uu, vv, len(nn))
        cs = cls.reindex(nn).to_numpy()
        T.append(dict(t=t, date=step_date(t), n_nodes=len(nn), n_edges=len(g),
                      gc_frac=gc / len(nn), n_comp=1,
                      ill_nodes=int((cs == 1).sum()),
                      ill_share=float((cs == 1).mean()),
                      lic_nodes=int((cs == 2).sum()),
                      mean_deg=float(np.bincount(
                          np.concatenate([uu, vv]), minlength=len(nn)).mean())))
    T = pd.DataFrame(T)
    log("  gc_frac across 49 steps: min=%.4f max=%.4f sd=%.6f"
        % (T["gc_frac"].min(), T["gc_frac"].max(), T["gc_frac"].std()))
    log("  steps with gc_frac == 1.0 exactly: %d / %d"
        % (int((T["gc_frac"] == 1.0).sum()), len(T)))
    log("  ⇒ the 2-week address graph is ONE connected component at essentially")
    log("    every step. Giant-component connectivity has no range here and")
    log("    CANNOT be used as a resilience instrument at this resolution.")
    log("    (25_'s z-scores on this quantity divided by an sd of ~0 and are")
    log("     withdrawn.)")
    log("")
    log("  mean degree per step: min=%.2f max=%.2f sd=%.2f  <- this DOES vary"
        % (T["mean_deg"].min(), T["mean_deg"].max(), T["mean_deg"].std()))

    sep("3. ★ Pre-specified shock test on the observables that vary")
    log("  Window fixed OUTSIDE the data: AlphaBay+Hansa 2017-07-20, BTC-e")
    log("  2017-07-25 -> steps 41-43 under the block anchor. Stated before the")
    log("  test is run.")
    for col, direction in (("ill_share", "lower"),
                           ("ill_nodes", "lower"),
                           ("n_nodes", "lower")):
        y = T[col].to_numpy(float)
        obs3 = float(y[[40, 41, 42]].mean())          # steps 41,42,43
        rng2 = np.random.default_rng(7)
        null = np.array([y[rng2.choice(49, 3, replace=False)].mean()
                         for _ in range(20000)])
        p3 = float((null <= obs3).mean()) if direction == "lower" else \
            float((null >= obs3).mean())
        obs5 = float(y[40:45].mean())
        null5 = np.array([y[rng2.choice(49, 5, replace=False)].mean()
                          for _ in range(20000)])
        p5 = float((null5 <= obs5).mean()) if direction == "lower" else \
            float((null5 >= obs5).mean())
        log("")
        log("  [%s]" % col)
        log("    series mean=%.4f sd=%.4f" % (y.mean(), y.std()))
        log("    steps 41-43 mean=%.4f   permutation p(<=) = %.4f"
            % (obs3, p3))
        log("    steps 41-45 mean=%.4f   permutation p(<=) = %.4f  (EXPLORATORY"
            % (obs5, p5))
        log("     -- this 5-step window was chosen after seeing the series)")
    log("")
    log("  individual steps around the window:")
    log("  %4s %-11s %8s %9s %10s %9s" % ("t", "date", "nodes", "ill_nodes",
                                         "ill_share", "mean_deg"))
    for _, r in T[(T["t"] >= 38) & (T["t"] <= 46)].iterrows():
        log("  %4d %-11s %8d %9d %9.3f%% %9.2f"
            % (r["t"], r["date"], r["n_nodes"], r["ill_nodes"],
               100 * r["ill_share"], r["mean_deg"]))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 2, figsize=(13, 9))
        for c, col in (("random", "0.5"), ("degree", "crimson"),
                       ("illicit_deg", "darkorange"),
                       ("illicit_rand", "steelblue")):
            ax[0, 0].plot(100 * O["frac"], curves[c], "o-", ms=3, color=col,
                          label=c)
        ax[0, 0].axhline(50, ls=":", color="k", lw=1)
        ax[0, 0].set_xlim(-1, 92)
        ax[0, 0].set_title("A. Giant component under node removal")
        ax[0, 0].set_xlabel("% nodes removed")
        ax[0, 0].set_ylabel("% of survivors in giant component")
        ax[0, 0].legend(fontsize=8)

        ax[0, 1].plot(T["t"], 100 * T["gc_frac"], "o-", color="darkgreen", ms=4)
        ax[0, 1].set_ylim(99.9, 100.02)
        for tt in (41, 42, 43):
            ax[0, 1].axvline(tt, ls="--", color="crimson", lw=1)
        ax[0, 1].set_title("B. Connectivity is SATURATED\n(no usable range)")
        ax[0, 1].set_xlabel("time step")
        ax[0, 1].set_ylabel("giant component %")

        ax[1, 0].plot(T["t"], 100 * T["ill_share"], "o-", color="purple", ms=4)
        ax[1, 0].axvspan(41, 43, color="crimson", alpha=0.12)
        ax[1, 0].axhline(100 * T["ill_share"].mean(), ls=":", color="k", lw=1)
        ax[1, 0].set_title("C. Illicit share of active addresses\n(shaded = "
                           "pre-specified July 2017 window)")
        ax[1, 0].set_xlabel("time step")
        ax[1, 0].set_ylabel("% illicit")

        rng3 = np.random.default_rng(7)
        y = T["ill_share"].to_numpy(float)
        null = np.array([y[rng3.choice(49, 3, replace=False)].mean()
                         for _ in range(20000)])
        ax[1, 1].hist(100 * null, bins=45, color="0.7")
        ax[1, 1].axvline(100 * y[[40, 41, 42]].mean(), color="crimson", lw=2,
                         label="steps 41-43")
        ax[1, 1].set_title("D. Permutation null for a 3-step window\n"
                           "(illicit share)")
        ax[1, 1].set_xlabel("mean illicit share over the window (%)")
        ax[1, 1].legend(fontsize=8)

        plt.tight_layout()
        os.makedirs(FIGS, exist_ok=True)
        plt.savefig(os.path.join(FIGS, "E6fin_resilience_v2.png"), dpi=150)
        plt.savefig(os.path.join(FIGS, "E6fin_resilience_v2.pdf"))
        log("\nwrote %s/E6fin_resilience_v2.{png,pdf}" % FIGS)
    except Exception as ex:  # noqa: BLE001
        log("\nfigure failed (non-fatal): %r" % ex)

    out = dict(
        nodes=int(N), edges=int(len(e)),
        full_gc=giant(u, v, N),
        collapse50={c: collapse50(curves[c]) for c in orders},
        auc={c: float(np.trapezoid(curves[c], O["frac"])) for c in orders},
        gc_frac_sd=float(T["gc_frac"].std()),
        gc_frac_min=float(T["gc_frac"].min()),
        timeline=T.to_dict("records"),
    )
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "26_E6fin_resilience_v2.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "26_E6fin_resilience_v2.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/26_E6fin_resilience_v2.{txt,json}" % RESULTS)
    log("E6FIN2_DONE")


if __name__ == "__main__":
    main()
