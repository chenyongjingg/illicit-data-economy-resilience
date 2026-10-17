#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""21_validate_participation.py -- is a wallets_features row a *transaction
participation*, and is the row count therefore a per-time-step activity count?

20_ resolved the shape but not the meaning. Facts it established:

  * 1,268,260 rows, 822,942 addresses.
  * 347,569 rows are byte-identical duplicates; the count of duplicated
    (address, Time step) pairs is the *same* 347,569, and
    1,268,260 - 347,569 = 920,691, which is exactly the number of distinct
    (address, Time step) pairs.
  * `total_txs` is constant within an address and equals the address's ROW COUNT
    exactly (correlation 1.0000 across 822,942 addresses).
  * `num_timesteps_appeared_in` equals the DISTINCT (address, Time step) count.

The reading that fits all four: the file has one row per (address, transaction)
participation; every non-key column is an address-level aggregate, repeated; so
two transactions of one address inside one time step are byte-identical rows and
look like duplicates. Under that reading the row count for an (address, Time
step) cell is the number of transactions the address made in that step -- a real
intensity panel, and precisely what a persistence analysis needs.

That reading is attractive, and attractive readings are the ones to test. The
sharpest available test does not use this file at all. The transaction side of
the same release carries role-split edge lists:

    AddrTx_edgelist.csv : input_address, txId      (the address SENT in tx)
    TxAddr_edgelist.csv : txId, output_address     (the address RECEIVED in tx)

so the number of AddrTx rows for an address is that address's sender-transaction
count, measured from a different file by a different construction. If the
participation reading is right, it must equal `num_txs_as_sender` in
wallets_features -- an address-level field the edge list knows nothing about.

  Agreement  -> the participation reading survives, and row counts are counts.
  Disagreement -> the row counts are a replication artefact and every
                  per-step intensity statistic built on them is meaningless.

The check is run in both directions (senders via AddrTx, receivers via TxAddr),
and the per-time-step version is run too, since that is the quantity a panel
would actually use.
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


def find(name):
    for d in (ACT, TXN, BASE, os.path.join(BASE, "_derived")):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def main():
    log("=" * 78)
    log("Is a wallets_features row a transaction participation?")
    log("=" * 78)

    sep("0. Locate the role-split edge lists")
    at = find("AddrTx_edgelist.csv")
    ta = find("TxAddr_edgelist.csv")
    log("  AddrTx_edgelist.csv (sender side):  %s" % at)
    log("  TxAddr_edgelist.csv (receiver side): %s" % ta)
    if at is None or ta is None:
        log("  MISSING -- cannot run the check")
        return

    sep("1. Read the edge lists")
    addr_tx = pd.read_csv(at)
    tx_addr = pd.read_csv(ta)
    log("  AddrTx rows: %d  cols=%s" % (len(addr_tx), list(addr_tx.columns)))
    log("  TxAddr rows: %d  cols=%s" % (len(tx_addr), list(tx_addr.columns)))
    log("  total edges: %d" % (len(addr_tx) + len(tx_addr)))
    log("  README claims AddrTx 477,117 / TxAddr 837,124 / sum 1,314,241")
    log("  distinct txId in AddrTx: %d ; in TxAddr: %d"
        % (addr_tx["txId"].nunique(), tx_addr["txId"].nunique()))

    sep("2. Sender counts from the edge list vs `num_txs_as_sender`")
    sender_edges = addr_tx.groupby("input_address").size()
    sender_edges.index.name = "address"
    log("  distinct sending addresses in AddrTx: %d" % len(sender_edges))

    wf = pd.read_csv(os.path.join(ACT, "wallets_features.csv"), usecols=[
        "address", "Time step", "num_txs_as_sender", "num_txs_as receiver",
        "total_txs", "num_timesteps_appeared_in"], low_memory=False)
    addr_lvl = wf.groupby("address").agg(
        stated_sender=("num_txs_as_sender", "first"),
        stated_receiver=("num_txs_as receiver", "first"),
        stated_total=("total_txs", "first"),
        stated_steps=("num_timesteps_appeared_in", "first"),
        rows=("Time step", "size"),
        distinct_steps=("Time step", "nunique"))
    log("  addresses in wallets_features: %d" % len(addr_lvl))

    j = addr_lvl.join(sender_edges.rename("edge_sender_count"), how="left")
    j["edge_sender_count"] = j["edge_sender_count"].fillna(0).astype(int)
    both = j[j["stated_sender"] > 0]
    agree = int((both["stated_sender"] == both["edge_sender_count"]).sum())
    log("")
    log("  addresses with stated_sender > 0: %d" % len(both))
    log("  stated_sender == edge_sender_count: %d (%.2f%%)"
        % (agree, 100.0 * agree / max(len(both), 1)))
    d = both["stated_sender"] - both["edge_sender_count"]
    log("  difference (stated - edges): mean=%.4f median=%.1f min=%.0f max=%.0f"
        % (d.mean(), d.median(), d.min(), d.max()))
    log("  exact-zero difference rows: %d / %d (%.2f%%)"
        % (int((d == 0).sum()), len(d), 100.0 * (d == 0).mean()))
    log("  examples where they disagree (head):")
    dis = both[both["stated_sender"] != both["edge_sender_count"]]
    if len(dis):
        log(dis.head(6).to_string())
    else:
        log("    (none)")

    sep("3. The same check on the receiver side")
    recv_edges = tx_addr.groupby("output_address").size()
    recv_edges.index.name = "address"
    j2 = addr_lvl.join(recv_edges.rename("edge_recv_count"), how="left")
    j2["edge_recv_count"] = j2["edge_recv_count"].fillna(0).astype(int)
    both2 = j2[j2["stated_receiver"] > 0]
    agree2 = int((both2["stated_receiver"] == both2["edge_recv_count"]).sum())
    log("  addresses with stated_receiver > 0: %d" % len(both2))
    log("  stated_receiver == edge_recv_count: %d (%.2f%%)"
        % (agree2, 100.0 * agree2 / max(len(both2), 1)))
    d2 = both2["stated_receiver"] - both2["edge_recv_count"]
    log("  exact-zero difference rows: %d / %d (%.2f%%)"
        % (int((d2 == 0).sum()), len(d2), 100.0 * (d2 == 0).mean()))

    sep("4. The decisive one: does stated_sender + stated_receiver == rows?")
    tot = addr_lvl["stated_sender"] + addr_lvl["stated_receiver"]
    ok = int((tot == addr_lvl["rows"]).sum())
    log("  addresses where sender+receiver == row count: %d / %d (%.2f%%)"
        % (ok, len(addr_lvl), 100.0 * ok / len(addr_lvl)))
    dd = addr_lvl["rows"] - tot
    log("  difference (rows - roles): mean=%.4f median=%.1f max=%.0f"
        % (dd.mean(), dd.median(), dd.max()))
    log("")
    log("  If this holds, every row is one (address, transaction) participation")
    log("  and no row is a write artefact -- the 'duplicates' are distinct")
    log("  transactions that happen to be indistinguishable in this schema.")

    sep("5. Per-time-step check -- the quantity a panel would actually use")
    tf = pd.read_csv(os.path.join(TXN, "txs_features.csv"),
                     usecols=["txId", "Time step"], low_memory=False)
    log("  txs_features rows: %d ; distinct txId: %d"
        % (len(tf), tf["txId"].nunique()))
    step_of = tf.set_index("txId")["Time step"]
    for label, ed, col in (("sender", addr_tx, "input_address"),
                           ("receiver", tx_addr, "output_address")):
        e = ed.copy()
        e["Time step"] = e["txId"].map(step_of)
        unmapped = int(e["Time step"].isna().sum())
        e = e.dropna(subset=["Time step"])
        e["Time step"] = e["Time step"].astype(int)
        cnt = e.groupby([col, "Time step"]).size().rename("n").reset_index()
        cnt.columns = ["address", "Time step", "edge_n"]
        obs = wf.groupby(["address", "Time step"]).size().rename(
            "row_n").reset_index()
        m = obs.merge(cnt, on=["address", "Time step"], how="left")
        m["edge_n"] = m["edge_n"].fillna(0).astype(int)
        eq = int((m["row_n"] == m["edge_n"]).sum())
        # the cell counts are only comparable once summed per role; compare a
        # sender-cell count against the sender-edge count for that same cell
        log("")
        log("  [%s side] cells in wallets_features: %d ; unmapped txId: %d"
            % (label, len(obs), unmapped))
        log("    cells whose row count equals the edge count: %d (%.2f%%)"
            % (eq, 100.0 * eq / len(m)))
        log("    sum(row_n)=%d  sum(edge_n)=%d" % (m["row_n"].sum(),
                                                  m["edge_n"].sum()))
        log("    NOTE: row_n counts BOTH roles, edge_n counts one role, so the")
        log("    per-cell equality is expected to fail by the other role's")
        log("    contribution. The informative number is the TOTAL in section 4.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "21_elliptic_participation.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/21_elliptic_participation.txt" % RESULTS)
    log("ELLIPTIC_PARTICIPATION_DONE")


if __name__ == "__main__":
    main()
