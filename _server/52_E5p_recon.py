#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""52_E5p_recon.py -- measure the sizes that decide E5p's design, before writing it.

Sizes are measured, not assumed. On a 14-vCPU pod a temporal GNN over 822,942
nodes is a different project from one over the labelled subgraph, and choosing
between them by guesswork would produce either a job that cannot finish or a
result that answers a different question than the one asked.

Also settles the leakage question up front: the task is
    at an address's FIRST observed step t0, predict whether it is seen again
and that is only a prediction if features come from t0 alone.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

BASE = "/root/cis/data/EllipticPlusPlus-main"
ACT = os.path.join(BASE, "Actors Dataset")
OUT = "/root/cis/results/52_E5p_recon.json"


def main():
    t0 = time.time()
    r = {}

    wc = pd.read_csv(os.path.join(ACT, "wallets_classes.csv"))
    r["wallets_classes_cols"] = list(wc.columns)
    r["n_addresses"] = int(len(wc))
    cls = wc.iloc[:, -1] if "class" not in wc.columns else wc["class"]
    r["class_counts"] = {str(k): int(v) for k, v in cls.value_counts().items()}
    labelled = set(wc.loc[cls.isin([1, 2]), "address"]) if "address" in wc.columns else set()
    r["n_labelled"] = len(labelled)

    wf = pd.read_csv(os.path.join(ACT, "wallets_features.csv"),
                     usecols=["address", "Time step"])
    r["n_wallet_rows"] = int(len(wf))
    r["step_min"] = int(wf["Time step"].min())
    r["step_max"] = int(wf["Time step"].max())
    r["n_steps"] = int(wf["Time step"].nunique())

    pairs = wf[["address", "Time step"]].drop_duplicates()
    per = pairs.groupby("address")["Time step"].nunique().rename("n_steps")
    r["addresses_in_wallets_features"] = int(len(per))
    if labelled:
        sub = per[per.index.isin(labelled)]
        r["labelled_with_any_step"] = int(len(sub))
        r["labelled_recur_rate"] = float((sub >= 2).mean()) if len(sub) else None
        r["labelled_onestep_rate"] = float((sub == 1).mean()) if len(sub) else None
    r["all_recur_rate"] = float((per >= 2).mean())

    # adjacency restricted to the labelled subgraph -- the graph E5p would use
    aa = pd.read_csv(os.path.join(ACT, "AddrAddr_edgelist.csv"))
    r["addr_addr_cols"] = list(aa.columns)
    r["n_aa_edges"] = int(len(aa))
    if labelled and len(aa.columns) >= 2:
        c0, c1 = aa.columns[0], aa.columns[1]
        mask = aa[c0].isin(labelled) & aa[c1].isin(labelled)
        r["labelled_subgraph_edges"] = int(mask.sum())
        nodes = set(aa.loc[mask, c0]) | set(aa.loc[mask, c1])
        r["labelled_subgraph_nodes"] = len(nodes)

    r["seconds"] = round(time.time() - t0, 1)
    os.makedirs("/root/cis/results", exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(r, fh, ensure_ascii=False, indent=2)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
