#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""25_E6fin_resilience.py -- financial layer: structural resilience of the
labelled Bitcoin transaction graph.

E5-fin measured actor recurrence and its class effect failed its own specificity
check (C-48). This asks a different and more standard question, one that does not
route through the address-level class label at all:

  A. STRUCTURAL RESILIENCE. Build the address-address graph from real input->
     output pairs, then remove nodes and watch the giant component. Compare
     random removal against degree-targeted removal, and illicit-targeted removal
     against random-removal-inside-illicit. The quantity of interest is how much
     damage the graph absorbs before it fragments -- RQ1's measurement question
     and RQ3's intervention question in the same object.

  B. TIME-RESOLVED CONNECTIVITY, against an EXTERNAL date. The window spans
     blocks 391,200-487,975. Anchoring on the well-known block 400,000 =
     2016-02-25 gives ~144 blocks/day, which places the July 2017 enforcement
     wave (AlphaBay and Hansa both taken down 2017-07-20, BTC-e on 2017-07-25)
     at the step 41/42 boundary.

     ★ The date is derived from an external fact about the world, NOT from this
     dataset. That is what makes it a test rather than a description. The
     prediction is directional and falsifiable: if the labelled illicit subgraph
     responds to that enforcement wave, connectivity and illicit activity should
     break around steps 41-42, and the LICIT subgraph -- not a target of that
     wave -- should not. If nothing happens, that is the result.

     The block->date map is approximate; +/-1 step is the honest precision, and
     both 41 and 42 are reported rather than the one that looks better.

Everything here is structural. No survival model, no p-value quoted on a
heterogeneous pooled estimate.
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

BLOCK0 = 391200
PER_STEP = 2016
ANCHOR_BLOCK = 400000          # 2016-02-25, external well-known fact
ANCHOR_DAY = 16856             # days since epoch for 2016-02-25


def step_date(t):
    """Approximate median calendar date of time step t (144 blocks/day)."""
    import datetime as dt
    mid = BLOCK0 + (t - 0.5) * PER_STEP
    day = ANCHOR_DAY + (mid - ANCHOR_BLOCK) / 144.0
    return dt.date(1970, 1, 1) + dt.timedelta(days=day)


def giant(edges_u, edges_v, n_nodes):
    """Size of the largest connected component, and the component labels."""
    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        g = coo_matrix((np.ones(len(edges_u), dtype=np.int8),
                        (edges_u, edges_v)), shape=(n_nodes, n_nodes))
        g = g.tocsr()
        ncomp, lab = connected_components(g, directed=False)
        if ncomp == 0:
            return 0, lab
        return int(np.bincount(lab).max()), lab
    except ImportError:
        # union-find fallback
        parent = np.arange(n_nodes)

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b in zip(edges_u, edges_v):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        roots = np.array([find(i) for i in range(n_nodes)])
        _, lab = np.unique(roots, return_inverse=True)
        return int(np.bincount(lab).max()), lab


def main():
    log("=" * 78)
    log("E6-fin  Structural resilience of the labelled Bitcoin transaction graph")
    log("=" * 78)

    sep("0. The clock, from an external anchor")
    log("  steps span blocks %d .. %d at %d blocks/step"
        % (BLOCK0, BLOCK0 + 49 * PER_STEP - 1, PER_STEP))
    log("  anchor: block %d = 2016-02-25 (external), %.1f blocks/day"
        % (ANCHOR_BLOCK, 144.0))
    for t in (1, 10, 20, 30, 40, 41, 42, 43, 49):
        log("    step %2d  ~ %s" % (t, step_date(t)))
    log("")
    log("  the July 2017 enforcement wave (AlphaBay + Hansa 2017-07-20, BTC-e")
    log("  2017-07-25) lands at the step 41/42 boundary under this map.")

    sep("1. Build the address-address edges with their time step")
    tf = pd.read_csv(os.path.join(TXN, "txs_features.csv"),
                     usecols=["txId", "Time step"], low_memory=False)
    step_of = tf.set_index("txId")["Time step"]
    at = pd.read_csv(os.path.join(ACT, "AddrTx_edgelist.csv"))
    ta = pd.read_csv(os.path.join(ACT, "TxAddr_edgelist.csv"))
    e = at.merge(ta, on="txId", how="inner")
    log("  raw input->output pairs: %d" % len(e))
    e = e[e["input_address"] != e["output_address"]]
    log("  after dropping self-loops (change addresses): %d" % len(e))
    e["Time step"] = e["txId"].map(step_of)
    e = e.dropna(subset=["Time step"])
    e["Time step"] = e["Time step"].astype(int)
    log("  with a time step: %d over steps %d..%d"
        % (len(e), e["Time step"].min(), e["Time step"].max()))

    wc = pd.read_csv(os.path.join(ACT, "wallets_classes.csv"))
    cls = wc.set_index("address")["class"]

    sep("2. A. STRUCTURAL RESILIENCE -- giant component under node removal")
    nodes = pd.Index(pd.unique(pd.concat([e["input_address"],
                                          e["output_address"]], ignore_index=True)))
    idx = pd.Series(np.arange(len(nodes)), index=nodes)
    log("  nodes: %d ; edges: %d" % (len(nodes), len(e)))
    u = e["input_address"].map(idx).to_numpy()
    v = e["output_address"].map(idx).to_numpy()
    node_class = cls.reindex(nodes).to_numpy()
    deg = np.bincount(np.concatenate([u, v]), minlength=len(nodes))

    log("  degree: mean=%.3f median=%.0f p99=%.0f max=%d"
        % (deg.mean(), np.median(deg), np.percentile(deg, 99), deg.max()))
    for k in (1, 2, 3):
        m = node_class == k
        if m.sum():
            log("    %-9s n=%7d  mean degree=%7.3f  median=%.0f"
                % (NAMES[k], m.sum(), deg[m].mean(), np.median(deg[m])))

    full_gc, _ = giant(u, v, len(nodes))
    log("  full graph: giant component = %d nodes (%.4f%% of all nodes)"
        % (full_gc, 100.0 * full_gc / len(nodes)))

    rng = np.random.default_rng(20260924)
    rnd_order = rng.permutation(len(nodes))
    deg_order = np.argsort(-deg)
    ill = np.where(node_class == 1)[0]
    ill_order = np.concatenate([
        ill[np.argsort(-deg[ill])],
        np.setdiff1d(rnd_order, ill)])
    ill_rand = np.concatenate([rng.permutation(ill),
                               np.setdiff1d(rnd_order, ill)])

    fracs = np.arange(0, 0.951, 0.05)
    curves = {}
    log("")
    log("  %6s %12s %12s %12s %12s"
        % ("removed", "random", "degree", "illicit-first", "illicit-rand"))
    order_rows = []
    for f in fracs:
        k = int(f * len(nodes))
        row = {"frac": float(f)}
        for name, order in (("random", rnd_order), ("degree", deg_order),
                            ("illicit", ill_order), ("illicit_rand", ill_rand)):
            keep = np.ones(len(nodes), dtype=bool)
            keep[order[:k]] = False
            m = keep[u] & keep[v]
            nk = int(keep.sum())
            if m.sum() == 0 or nk == 0:
                row[name] = 0.0
            else:
                relab = -np.ones(len(nodes), dtype=np.int64)
                relab[keep] = np.arange(nk)
                gc, _ = giant(relab[u[m]], relab[v[m]], nk)
                row[name] = 100.0 * gc / nk
        order_rows.append(row)
        if round(f * 20) % 2 == 0 or f >= 0.5:
            log("  %5.0f%% %11.2f%% %11.2f%% %11.2f%% %11.2f%%"
                % (100 * f, row["random"], row["degree"], row["illicit"],
                   row["illicit_rand"]))
    O = pd.DataFrame(order_rows)
    curves = {c: O[c].to_numpy() for c in ("random", "degree", "illicit",
                                           "illicit_rand")}

    def collapse50(y):
        """Fraction removed at which the giant component first falls below 50%."""
        below = np.where(y < 50.0)[0]
        return float(O["frac"].iloc[below[0]]) if len(below) else None

    log("")
    log("  fraction removed to take the giant component below 50%%:")
    for c in ("random", "degree", "illicit", "illicit_rand"):
        log("    %-14s %s" % (c, collapse50(curves[c])))
    log("  AUC of the giant-component curve (higher = more resilient):")
    for c in ("random", "degree", "illicit", "illicit_rand"):
        log("    %-14s %.2f" % (c, float(np.trapezoid(curves[c], O["frac"]))))

    sep("3. B. TIME-RESOLVED CONNECTIVITY")
    rows = []
    for t in range(1, 50):
        g = e[e["Time step"] == t]
        if len(g) == 0:
            continue
        nn = pd.unique(pd.concat([g["input_address"], g["output_address"]],
                                 ignore_index=True))
        i2 = pd.Series(np.arange(len(nn)), index=nn)
        uu = g["input_address"].map(i2).to_numpy()
        vv = g["output_address"].map(i2).to_numpy()
        gc, lab = giant(uu, vv, len(nn))
        sizes = np.bincount(lab)
        nc = int((sizes > 0).sum())
        cs = cls.reindex(nn).to_numpy()
        rows.append(dict(
            t=t, date=str(step_date(t)), n_nodes=len(nn), n_edges=len(g),
            gc=gc, gc_frac=gc / len(nn), n_comp=nc,
            ill_nodes=int((cs == 1).sum()),
            ill_share=float((cs == 1).mean()),
            mean_deg=float(np.bincount(np.concatenate([uu, vv]),
                                       minlength=len(nn)).mean())))
    T = pd.DataFrame(rows)
    log("  %3s %-11s %8s %8s %9s %8s %8s"
        % ("t", "date", "nodes", "edges", "gc_frac", "n_comp", "ill%"))
    for _, r in T.iterrows():
        mark = ""
        if r["t"] in (41, 42, 43):
            mark = "  <<< enforcement window"
        log("  %3d %-11s %8d %8d %8.4f %8d %7.3f%%%s"
            % (r["t"], r["date"], r["n_nodes"], r["n_edges"], r["gc_frac"],
               r["n_comp"], 100 * r["ill_share"], mark))

    sep("4. The shock test -- is anything unusual at steps 41-42?")
    z = (T["gc_frac"] - T["gc_frac"].mean()) / T["gc_frac"].std()
    Tz = pd.DataFrame({"t": T["t"], "z": z}).sort_values("z")
    log("  gc_frac: mean=%.4f sd=%.4f" % (T["gc_frac"].mean(),
                                          T["gc_frac"].std()))
    log("  5 lowest steps by gc_frac: %s"
        % list(Tz.head(5).itertuples(index=False, name=None)))
    log("  5 highest steps by gc_frac: %s"
        % list(Tz.tail(5).itertuples(index=False, name=None)))
    log("")
    for t in (41, 42):
        r = T[T["t"] == t].iloc[0]
        log("  step %d (%s): gc_frac=%.4f  z=%+.2f  ill_share=%.3f%%"
            % (t, r["date"], r["gc_frac"], z.iloc[t - 1], 100 * r["ill_share"]))
    log("")
    log("  illicit share across steps: mean=%.3f%% sd=%.3f%%"
        % (100 * T["ill_share"].mean(), 100 * T["ill_share"].std()))
    zz = (T["ill_share"] - T["ill_share"].mean()) / T["ill_share"].std()
    log("  largest 5 |z| for illicit share: %s"
        % list(pd.DataFrame({"t": T["t"], "z": zz}).reindex(
            zz.abs().sort_values(ascending=False).index).head(5)
            .itertuples(index=False, name=None)))

    # ----------------------------------------------------------------- figure
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 2, figsize=(13, 9))

        for c, lbl, col in (("random", "random", "0.5"),
                            ("degree", "degree-targeted", "crimson"),
                            ("illicit", "illicit-first (deg)", "darkorange"),
                            ("illicit_rand", "illicit-first (random)", "steelblue")):
            ax[0, 0].plot(100 * O["frac"], curves[c], "o-", ms=3, color=col,
                          label=lbl)
        ax[0, 0].axhline(50, ls=":", color="k", lw=1)
        ax[0, 0].set_title("A. Giant component under node removal")
        ax[0, 0].set_xlabel("% nodes removed")
        ax[0, 0].set_ylabel("% of surviving nodes in giant component")
        ax[0, 0].legend(fontsize=8)

        ax[0, 1].plot(T["t"], 100 * T["gc_frac"], "o-", color="darkgreen", ms=4)
        for tt in (41, 42):
            ax[0, 1].axvline(tt, ls="--", color="crimson", lw=1)
        ax[0, 1].set_title("B. Time-resolved connectivity\n(dashed = July 2017 wave)")
        ax[0, 1].set_xlabel("time step")
        ax[0, 1].set_ylabel("giant component %")

        ax[1, 0].plot(T["t"], 100 * T["ill_share"], "o-", color="purple", ms=4)
        for tt in (41, 42):
            ax[1, 0].axvline(tt, ls="--", color="crimson", lw=1)
        ax[1, 0].set_title("C. Illicit share of active addresses")
        ax[1, 0].set_xlabel("time step")
        ax[1, 0].set_ylabel("% illicit")

        ax[1, 1].plot(T["t"], T["n_nodes"], "o-", color="steelblue", ms=4,
                      label="nodes")
        ax[1, 1].plot(T["t"], T["n_edges"], "s-", color="crimson", ms=4,
                      label="edges")
        ax[1, 1].set_yscale("log")
        for tt in (41, 42):
            ax[1, 1].axvline(tt, ls="--", color="crimson", lw=1)
        ax[1, 1].set_title("D. Active nodes and edges per step")
        ax[1, 1].set_xlabel("time step")
        ax[1, 1].legend(fontsize=8)

        plt.tight_layout()
        os.makedirs(FIGS, exist_ok=True)
        plt.savefig(os.path.join(FIGS, "E6fin_resilience.png"), dpi=150)
        plt.savefig(os.path.join(FIGS, "E6fin_resilience.pdf"))
        log("\nwrote %s/E6fin_resilience.{png,pdf}" % FIGS)
    except Exception as ex:  # noqa: BLE001
        log("\nfigure failed (non-fatal): %r" % ex)

    out = dict(
        nodes=int(len(nodes)), edges=int(len(e)), full_gc=int(full_gc),
        collapse50={c: collapse50(curves[c])
                    for c in ("random", "degree", "illicit", "illicit_rand")},
        auc={c: float(np.trapezoid(curves[c], O["frac"]))
             for c in ("random", "degree", "illicit", "illicit_rand")},
        timeline=T.to_dict("records"),
        gc_z41=float(z.iloc[40]), gc_z42=float(z.iloc[41]),
    )
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "25_E6fin_resilience.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "25_E6fin_resilience.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/25_E6fin_resilience.{txt,json}" % RESULTS)
    log("E6FIN_DONE")


if __name__ == "__main__":
    main()
