#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""53a_E5p_probe.py -- probe the two things E5p's design hinges on, before it is written.

QUESTION 1: which `wallets_features` columns are PER-STEP, and which are
address-level LIFETIME aggregates repeated on every row?

This decides leakage. 05_ established that a row is one (address, *transaction*)
participation and that `total_txs` / `num_txs_as_sender` / `num_txs_as_receiver`
are constant within address. If that is true of a column more generally, the
column is computed over the address's whole lifetime -- including steps AFTER
the entry step t0 -- and using it as a "feature at t0" would feed the model the
answer. `num_timesteps_appeared_in` is the label in disguise. Measured, not
assumed: for every column we report the fraction of addresses on which the
column takes more than one distinct value.

QUESTION 2: does the timed address->address construction actually close?
AddrTx_edgelist (input_address, txId) x TxAddr_edgelist (txId, output_address)
joined on txId, with txs_features giving each tx a Time step. We measure the
join size, tx-id coverage of txs_features, and the per-step event counts -- the
event stream a TGN would consume. A silent inner-join drop here would shrink the
graph without any error.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

BASE = "/root/cis/data/EllipticPlusPlus-main"
ACT = os.path.join(BASE, "Actors Dataset")
TXD = os.path.join(BASE, "Transactions Dataset")
OUT = "/root/cis/results/53a_E5p_probe.json"


def main():
    t0 = time.time()
    r = {}

    # ---- Q1: per-address column variation ---------------------------------
    wf = pd.read_csv(os.path.join(ACT, "wallets_features.csv"))
    r["wf_shape"] = list(wf.shape)
    r["wf_cols"] = list(wf.columns)
    key = "address"
    num_cols = [c for c in wf.columns if c not in (key, "Time step")]
    g = wf.groupby(key, sort=False)
    var = {}
    for c in num_cols:
        # nunique over the address's rows; >1 means the column is not a
        # constant-within-address lifetime aggregate.
        nu = g[c].nunique(dropna=False)
        var[c] = float((nu > 1).mean())
    r["frac_addresses_col_varies"] = var
    r["cols_constant_within_address"] = sorted([c for c, v in var.items() if v == 0.0])
    r["cols_varying_within_address"] = sorted([c for c, v in var.items() if v > 0.0])

    # rows per (address, step) -- the participation count
    per = wf.groupby([key, "Time step"], sort=False).size()
    r["n_addr_step_cells"] = int(len(per))
    r["rows_per_cell_max"] = int(per.max())
    r["rows_per_cell_mean"] = float(per.mean())

    # t0 distribution over the labelled cohort
    wc = pd.read_csv(os.path.join(ACT, "wallets_classes.csv"))
    lab = wc.loc[wc["class"].isin([1, 2]), ["address", "class"]]
    first = wf.groupby(key, sort=False)["Time step"].min().rename("t0")
    last = wf.groupby(key, sort=False)["Time step"].max().rename("t1")
    nst = wf.groupby(key, sort=False)["Time step"].nunique().rename("nsteps")
    coh = lab.join(first, on="address").join(last, on="address").join(nst, on="address")
    coh = coh.dropna(subset=["t0"])
    coh["t0"] = coh["t0"].astype(int)
    coh["recur"] = (coh["nsteps"] >= 2).astype(int)
    r["cohort_n"] = int(len(coh))
    r["cohort_recur_rate"] = float(coh["recur"].mean())
    r["cohort_by_class"] = {
        str(k): {"n": int(v["recur"].size), "recur_rate": float(v["recur"].mean())}
        for k, v in coh.groupby("class")
    }
    r["t0_hist"] = {str(int(k)): int(v) for k, v in coh["t0"].value_counts().sort_index().items()}
    # recurrence by t0 -- the ceiling
    byt = coh.groupby("t0")["recur"].agg(["size", "mean"])
    r["recur_by_t0"] = {str(int(k)): [int(a), round(float(b), 5)]
                        for k, (a, b) in byt.iterrows()}
    del wf, g

    # ---- Q2: the timed address->address construction -----------------------
    at = pd.read_csv(os.path.join(ACT, "AddrTx_edgelist.csv"))
    ta = pd.read_csv(os.path.join(ACT, "TxAddr_edgelist.csv"))
    tx = pd.read_csv(os.path.join(TXD, "txs_features.csv"),
                     usecols=["txId", "Time step"])
    r["n_addrtx"] = int(len(at))
    r["n_txaddr"] = int(len(ta))
    r["n_txs_features"] = int(len(tx))
    r["addrtx_txid_unique"] = int(at["txId"].nunique())
    r["txaddr_txid_unique"] = int(ta["txId"].nunique())
    r["txs_features_txid_unique"] = int(tx["txId"].nunique())
    r["txs_step_min"] = int(tx["Time step"].min())
    r["txs_step_max"] = int(tx["Time step"].max())

    s_at = set(at["txId"].unique())
    s_ta = set(ta["txId"].unique())
    s_tx = set(tx["txId"].unique())
    # The join is inner, so a tx id missing from txs_features would silently
    # lose its edges. Count all three, and the intersection explicitly.
    r["txid_in_addrtx_not_features"] = int(len(s_at - s_tx))
    r["txid_in_txaddr_not_features"] = int(len(s_ta - s_tx))
    r["txid_in_both_edges"] = int(len(s_at & s_ta))
    r["txid_in_both_and_features"] = int(len(s_at & s_ta & s_tx))

    m = at.merge(ta, on="txId", how="inner")
    r["join_rows_naive"] = int(len(m))
    if m.empty:
        r["join_note"] = "EMPTY JOIN -- address->address construction failed"
    else:
        m = m.merge(tx, on="txId", how="inner")
        r["join_rows_with_time"] = int(len(m))
        # address != address: self-loops (an address paying itself, or tx with
        # the same address on both sides) carry no relational information.
        same = m["input_address"].values == m["output_address"].values
        r["self_loop_rows"] = int(same.sum())
        m = m.loc[~same]
        r["edges_after_dropping_self_loops"] = int(len(m))
        r["step_min"] = int(m["Time step"].min())
        r["step_max"] = int(m["Time step"].max())
        ev = m.groupby("Time step").size()
        r["events_per_step"] = {str(int(k)): int(v) for k, v in ev.items()}
        r["events_per_step_mean"] = float(ev.mean())
        n_un = int(pd.unique(np.concatenate([
            m["input_address"].values, m["output_address"].values])).size)
        r["timed_graph_nodes"] = n_un
        coh_set = set(coh["address"])
        both = m["input_address"].isin(coh_set).values & m["output_address"].isin(coh_set).values
        r["edges_within_cohort"] = int(both.sum())
        r["frac_edges_within_cohort"] = float(both.mean())
        one = (m["input_address"].isin(coh_set).values
               | m["output_address"].isin(coh_set).values)
        r["edges_touching_cohort"] = int(one.sum())

    r["seconds"] = round(time.time() - t0, 1)
    os.makedirs("/root/cis/results", exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(r, fh, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in r.items()
                      if k not in ("t0_hist", "recur_by_t0", "events_per_step")},
                     ensure_ascii=False, indent=2)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
