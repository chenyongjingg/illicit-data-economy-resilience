#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""22_validate_percell.py -- verify the per-(address, time step) transaction count.

21_ confirmed the aggregate: for 822,939 of 822,942 addresses,
`num_txs_as_sender + num_txs_as receiver` equals the address's row count in
wallets_features, with maximum difference 0. That establishes that a row is one
(address, transaction) participation.

It does not yet establish the thing a panel analysis would actually consume: the
number of transactions an address made in each TIME STEP. 21_'s section 5
compared a cell's row count against one role's edge count, which is the wrong
comparison and it said so -- row_n counts both roles, edge_n one. The correct
identity is per cell:

    rows(address, step) == sender_edges(address, step) + receiver_edges(address, step)

This matters beyond bookkeeping. If it holds, the row count is a verified
per-step activity intensity and a persistence model can be built on it. If it
fails, the time-step label is not reliable at cell level even though the totals
are right, and the cell-level panel must be abandoned while the address-level
one survives.

Also reports the change-address rate, since an address appearing as both input
and output of the same transaction is the obvious way the two role counts could
overlap and inflate a cell.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

BASE = "/root/cis/data/EllipticPlusPlus-main"
ACT = os.path.join(BASE, "Actors Dataset")
TXN = os.path.join(BASE, "Transactions Dataset")
RESULTS = "/root/cis/results"

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


def main():
    log("=" * 78)
    log("Per-cell verification: rows(address, step) == sender_edges + receiver_edges")
    log("=" * 78)

    tf = pd.read_csv(os.path.join(TXN, "txs_features.csv"),
                     usecols=["txId", "Time step"], low_memory=False)
    step_of = tf.set_index("txId")["Time step"]
    log("  txId -> Time step map: %d entries, steps %s..%s"
        % (len(step_of), step_of.min(), step_of.max()))

    at = pd.read_csv(os.path.join(ACT, "AddrTx_edgelist.csv"))
    ta = pd.read_csv(os.path.join(ACT, "TxAddr_edgelist.csv"))

    sep("0. Change addresses -- an address that is both input and output")
    at_tx = at.groupby("txId")["input_address"].apply(set)
    ta_tx = ta.groupby("txId")["output_address"].apply(set)
    common = at_tx.index.intersection(ta_tx.index)
    log("  txs with both input and output edges: %d" % len(common))
    n_both = 0
    for t in common:
        n_both += len(at_tx[t] & ta_tx[t])
    log("  (tx, address) pairs where the address is BOTH input and output: %d"
        % n_both)
    log("  -> these would be counted once per role by the edge lists")

    sep("1. Build per-cell counts from the edge lists")
    frames = []
    for ed, col, role in ((at, "input_address", "sender"),
                          (ta, "output_address", "receiver")):
        e = ed.rename(columns={col: "address"}).copy()
        e["Time step"] = e["txId"].map(step_of)
        e = e.dropna(subset=["Time step"])
        e["Time step"] = e["Time step"].astype(int)
        # a (address, txId) pair repeated would be a duplicated edge; count
        # distinct transactions, not edge rows, to match the participation unit
        e = e[["address", "txId", "Time step"]].drop_duplicates()
        e["role"] = role
        frames.append(e)
    edges = pd.concat(frames, ignore_index=True)
    log("  distinct (address, txId, step, role) rows: %d" % len(edges))

    cell = edges.groupby(["address", "Time step"]).size().rename("edge_n")
    log("  distinct (address, step) cells from edges: %d" % len(cell))
    log("  sum(edge_n) = %d" % int(cell.sum()))

    sep("2. Compare against the wallets_features cells")
    wf = pd.read_csv(os.path.join(ACT, "wallets_features.csv"),
                     usecols=["address", "Time step"], low_memory=False)
    obs = wf.groupby(["address", "Time step"]).size().rename("row_n")
    log("  distinct (address, step) cells from wallets_features: %d" % len(obs))
    log("  sum(row_n) = %d" % int(obs.sum()))

    m = obs.to_frame().join(cell, how="outer")
    m["row_n"] = m["row_n"].fillna(0).astype(int)
    m["edge_n"] = m["edge_n"].fillna(0).astype(int)
    log("")
    log("  cells present in both: %d" % int(((m["row_n"] > 0) &
                                             (m["edge_n"] > 0)).sum()))
    log("  cells only in wallets_features: %d" % int(((m["row_n"] > 0) &
                                                      (m["edge_n"] == 0)).sum()))
    log("  cells only in edges:            %d" % int(((m["row_n"] == 0) &
                                                      (m["edge_n"] > 0)).sum()))

    eq = int((m["row_n"] == m["edge_n"]).sum())
    log("")
    log("  ★ cells where row_n == edge_n: %d / %d (%.4f%%)"
        % (eq, len(m), 100.0 * eq / len(m)))
    d = m["row_n"] - m["edge_n"]
    log("  difference (rows - edges): mean=%.6f median=%.1f min=%d max=%d"
        % (d.mean(), d.median(), d.min(), d.max()))
    log("  exact-zero difference: %d (%.4f%%)"
        % (int((d == 0).sum()), 100.0 * (d == 0).mean()))
    log("")
    log("  distribution of |difference| (head):")
    log(m.assign(ad=d.abs()).groupby("ad").size().head(10).to_string())

    sep("3. Where they disagree, how badly?")
    bad = m[m["row_n"] != m["edge_n"]]
    if len(bad):
        log("  disagreeing cells: %d (%.4f%%)" % (len(bad), 100.0 * len(bad) / len(m)))
        log("  share of total participation volume in those cells: %.4f%%"
            % (100.0 * bad["row_n"].sum() / m["row_n"].sum()))
        log("  head:")
        log(bad.head(10).to_string())
        log("")
        log("  concentration: the top 20 disagreeing cells hold %.2f%% of the"
            % (100.0 * bad.nlargest(20, "row_n")["row_n"].sum() / max(bad["row_n"].sum(), 1)))
        log("  disagreement volume.")
    else:
        log("  none")

    sep("4. Verdict input")
    log("  A high exact-match rate means the row count IS the per-step")
    log("  transaction count and a cell-level intensity panel is defensible.")
    log("  The address-level panel is unaffected either way: 21_ already")
    log("  established it on an independent object.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "22_elliptic_percell.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/22_elliptic_percell.txt" % RESULTS)
    log("ELLIPTIC_PERCELL_DONE")


if __name__ == "__main__":
    main()
