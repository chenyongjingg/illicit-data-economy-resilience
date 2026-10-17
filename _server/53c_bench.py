#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""53c_bench.py -- measure the two costs that decide E5p's shape, with printing.

The first TGNMemory smoke (53b) was started and had to be killed after ~19
minutes without reaching the end of its first variant. That is itself the
finding: at 57,612 events per time step, `TGNMemory.update_state` is far more
expensive than the shape of the operation suggests, because both
`_update_msg_store` and `_compute_msg` do PER-NODE Python work (`perm.split`,
`[msg_store[i] for i in ...]`, `torch.cat` over one small tensor per node).
The cost therefore scales with the number of DISTINCT NODES touched in a step,
not with the number of events.

So measure that, and measure what deduplication buys, rather than guessing:

  Q1  how many (src, dst, step) triples are duplicates? Multiplicity is real
      information for a degree feature, but a repeated parallel edge adds
      nothing to a mean aggregation -- and it is paid for per event.
  Q2  what does `update_state` actually cost per step, at full / deduped /
      cohort-restricted event scale? Timed with per-step printing so a stall is
      visible as a stall rather than as silence.
  Q3  does a gradient still reach the GRUCell and TimeEncoder on the eval-mode
      path E5p uses? (Eval mode changes only the ORDER of store/apply inside
      `update_state`; it must not deaden the graph.)
"""
import json
import sys
import time

import numpy as np
import pandas as pd
import torch

from torch_geometric.nn.models.tgn import (TGNMemory, IdentityMessage,
                                           LastAggregator)

ACT = "/root/cis/data/EllipticPlusPlus-main/Actors Dataset"
TXD = "/root/cis/data/EllipticPlusPlus-main/Transactions Dataset"
OUT = "/root/cis/results/53c_bench.json"
N_STEPS = 49
MEM, TDIM, RDIM = 64, 16, 3


def main():
    torch.set_num_threads(8)
    r = {}
    t0 = time.time()

    def log(*a):
        print("[53c %.1fs]" % (time.time() - t0), *a, flush=True)

    at = pd.read_csv(ACT + "/AddrTx_edgelist.csv")
    ta = pd.read_csv(ACT + "/TxAddr_edgelist.csv")
    txf = pd.read_csv(TXD + "/txs_features.csv", usecols=["txId", "Time step"])
    at.columns = ["src", "txId"]
    ta.columns = ["txId", "dst"]
    e = at.merge(ta, on="txId", how="inner").merge(txf, on="txId", how="inner")
    e = e[e["src"].values != e["dst"].values]
    r["n_edges_with_multiplicity"] = int(len(e))
    d = e.drop_duplicates(subset=["src", "dst", "Time step"])
    r["n_distinct_src_dst_step"] = int(len(d))
    r["dedup_shrink"] = round(1 - len(d) / len(e), 4)
    ev_full = e.groupby("Time step").size()
    ev_ded = d.groupby("Time step").size()
    r["events_per_step_full_mean"] = float(ev_full.mean())
    r["events_per_step_dedup_mean"] = float(ev_ded.mean())
    log("dedup", r["n_edges_with_multiplicity"], "->",
        r["n_distinct_src_dst_step"], "shrink", r["dedup_shrink"])

    wc = pd.read_csv(ACT + "/wallets_classes.csv")
    wc.columns = ["address", "class"]
    idx = pd.Series(np.arange(len(wc), dtype="int64"), index=wc["address"].values)
    n_nodes = len(wc)
    coh_set = set(wc.loc[wc["class"].isin([1, 2]), "address"])
    d2 = d.copy()
    d2["src_i"] = d2["src"].map(idx).astype("int64")
    d2["dst_i"] = d2["dst"].map(idx).astype("int64")
    both = d2["src"].isin(coh_set).values & d2["dst"].isin(coh_set).values
    r["cohort_internal_edges"] = int(both.sum())
    d_coh = d2[both]
    r["events_per_step_cohort_mean"] = float(d_coh.groupby("Time step").size().mean())
    log("cohort-internal edges", r["cohort_internal_edges"])

    def per_step_nodes(frame):
        uniq = []
        for t in range(1, N_STEPS + 1):
            s = frame[frame["Time step"] == t]
            u = np.unique(np.concatenate([s["src_i"].values, s["dst_i"].values]))
            uniq.append(len(u))
        return uniq

    log("counting distinct nodes per step (full)...")
    uniq_full = per_step_nodes(e.assign(
        src_i=e["src"].map(idx).astype("int64"),
        dst_i=e["dst"].map(idx).astype("int64")))
    uniq_ded = per_step_nodes(d2)
    uniq_coh = per_step_nodes(d_coh)
    r["distinct_nodes_per_step_full_mean"] = float(np.mean(uniq_full))
    r["distinct_nodes_per_step_dedup_mean"] = float(np.mean(uniq_ded))
    r["distinct_nodes_per_step_cohort_mean"] = float(np.mean(uniq_coh))
    log("distinct nodes/step full %.0f dedup %.0f cohort %.0f"
        % (r["distinct_nodes_per_step_full_mean"],
           r["distinct_nodes_per_step_dedup_mean"],
           r["distinct_nodes_per_step_cohort_mean"]))

    # ---- per-step timing on the eval-mode path ----------------------------
    def time_variant(frame, tag, n_steps=None, n_nodes=None):
        n_steps = n_steps or N_STEPS
        n_nodes = n_nodes or n_nodes_local
        torch.manual_seed(1)
        mem = TGNMemory(num_nodes=n_nodes, raw_msg_dim=RDIM, memory_dim=MEM,
                        time_dim=TDIM,
                        message_module=IdentityMessage(RDIM, MEM, TDIM),
                        aggregator_module=LastAggregator())
        with torch.no_grad():
            mem.train(False)
        mem.reset_state()
        head = torch.nn.Linear(MEM, 1)
        opt = torch.optim.Adam(list(mem.parameters()) + list(head.parameters()),
                               lr=1e-3)
        per, grads = [], {}
        for t in range(1, n_steps + 1):
            s = frame[frame["Time step"] == t]
            if len(s) == 0:
                continue
            ts = time.time()
            src = torch.from_numpy(s["src_i"].values)
            dst = torch.from_numpy(s["dst_i"].values)
            tt = torch.full((len(s),), t, dtype=torch.long)
            raw = torch.ones((len(s), RDIM))
            mem.update_state(src, dst, tt, raw)
            rsel = torch.from_numpy(
                np.random.default_rng(t).integers(0, n_nodes, 5400))
            logit = head(mem.memory[rsel]).squeeze(-1)
            y = torch.randint(0, 2, (5400,)).float()
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logit, y)
            opt.zero_grad()
            loss.backward()

            def gs(mod):
                ps = [p for p in mod.parameters() if p.grad is not None]
                return None if not ps else float(sum(float(p.grad.abs().sum())
                                                     for p in ps))

            if t in (1, 2, 3, n_steps):
                grads[str(t)] = {"gru": gs(mem.gru), "time_enc": gs(mem.time_enc),
                                 "head": gs(head)}
            opt.step()
            mem.detach()
            per.append(time.time() - ts)
        out = dict(tag=tag, mean_s=round(float(np.mean(per)), 3),
                   max_s=round(float(np.max(per)), 3),
                   total_s=round(float(np.sum(per)), 1),
                   n_steps=len(per), grads=grads,
                   grad_ok=all((g["gru"] or 0) > 0 and (g["time_enc"] or 0) > 0
                               and (g["head"] or 0) > 0 for g in grads.values()))
        log("variant", tag, "mean %.3fs/step total %.1fs grad_ok=%s"
            % (out["mean_s"], out["total_s"], out["grad_ok"]))
        return out

    n_nodes_local = n_nodes
    r["variant_full_eval"] = time_variant(
        e.assign(src_i=e["src"].map(idx).astype("int64"),
                 dst_i=e["dst"].map(idx).astype("int64")), "full_dedup_off")
    r["variant_dedup"] = time_variant(d2, "dedup_allnodes")
    r["variant_cohort"] = time_variant(d_coh, "dedup_cohortnodes")
    r["reserved_dedup_epoch_s"] = round(
        r["variant_dedup"]["mean_s"] * N_STEPS, 1)
    r["reserved_full_epoch_s"] = round(
        r["variant_full_eval"]["mean_s"] * N_STEPS, 1)
    r["seconds"] = round(time.time() - t0, 1)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(r, fh, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({k: v for k, v in r.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
