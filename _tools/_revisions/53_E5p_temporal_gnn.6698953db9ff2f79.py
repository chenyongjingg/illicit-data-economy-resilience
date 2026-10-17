#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""53_E5p_temporal_gnn.py -- E5p: the predictive half of the plan's E5.

THE PLAN ASKS FOR (plan v5, line 89)
    "TGN / TGAT 时序图神经网络，预测节点在 t+Delta 是否存续
     (AUC 对比 GraphSAGE、MLP 特征基线)"
    i.e. a temporal GNN predicting, at a horizon Delta, whether a node is still
    present -- scored by AUC against a GraphSAGE baseline and a feature-only MLP.

TASK, ANCHORED
    For every address, t0 = first observed step, t1 = last observed step.
        label_D(a) = 1[ t1_a - t0_a >= D ]
    Delta = 1 is `t1 > t0`, i.e. "observed in >= 2 distinct steps" -- exactly
    E5-fin's recurrence label. It is the degenerate end of the plan's Delta axis,
    not a different quantity.

    Delta is NOT specified by the plan, so it is a free parameter. It is
    PRE-REGISTERED here as DELTAS = (1, 3, 5), and reported for all three. A
    single Delta shown alone would not be interpretable: the label's prevalence
    falls steeply with Delta and so does the eligible set, for a reason that is
    construction, not behaviour -- see censoring and structural zero below. The
    censoring table is computed out to Delta = 20 so the trade-off is visible
    past the pre-registered range.

    CENSORING is first order: an address can satisfy `t1 - t0 >= D` only if a
    step at or after t0+D exists inside the 49-step window, i.e. iff
    t0 <= 49 - D. Addresses failing that are NOT silently relabelled 0 -- they
    are EXCLUDED from that Delta's eligible set, and the excluded share is
    reported per Delta and per class.

    STRUCTURAL ZERO: an address first seen at t0 = 49 can never satisfy D >= 1.
    Its label is 0 by construction. At D = 5 the same is true for every address
    with t0 >= 45. This is why "persistence falls with Delta" is partly an
    artefact of the window, and why per-t0 breakdowns are reported alongside.

    POPULATION is all 822,942 addresses. The survival label is defined for the
    "unknown" class too, so this arm does not inherit E5-fin's class-in-{1,2}
    gate -- taking the full population removes the "the labelled cohort is the
    least-persistent 32% of the dataset" scope problem from this arm. The
    class-in-{1,2} numbers are reported as a SUBSET of the same predictions (no
    separate model), for comparability with E5-fin.

================================ THE LEAKAGE RULE ============================
Everything the model sees at t0 must have been knowable AT t0. An address that
enters at t0 has at most (49 - t0) steps of room, and entry timing differs by
class, so any quantity computed over the FULL window encodes the answer.

Concretely -- and this measurement decided the entire feature design:

  MEASURED (53a, re-measured in-process here): all 55 non-key, non-time columns
  of `wallets_features.csv` are CONSTANT WITHIN ADDRESS; 0 of 55 vary. The file
  is not a per-step panel and not even a per-address table -- it is one row per
  (address, transaction) participation, carrying address-level LIFETIME
  aggregates repeated on every row. `num_timesteps_appeared_in` IS
  `n_steps_observed`, which at Delta=1 IS the label.

  => NOT ONE COLUMN of `wallets_features` is usable as a feature. Not "the
     obviously leaky ones are dropped": every one of them is dropped. The only
     thing taken from that file is `Time step`, used to define t0/t1 and
     therefore the label. (The label is defined over the full window -- that is
     the target, not a feature.)

  This matters MORE than usual for the MLP. The plan's own risk table fires a
  fallback ("降级为 GraphSAGE + 手工时序特征") when the temporal GNN improves
  little over the baseline. A baseline built from the provided table would be
  near-perfect at Delta = 1 for free, the honest GNN would look weak beside it,
  and the fallback would fire because of an artefact in the baseline rather than
  because of the GNN. So BOTH arms stand on the same point-in-time footing:
  every feature, in every arm, is rebuilt from the edge stream truncated at t0,
  and this is asserted with named checks, not asserted-by-convention:

    * own activity at step <= t0, from AddrTx x TxAddr joined through
      txs_features['Time step']: counts and per-transaction attributes of the
      transactions this address took part in;
    * graph structure from the same timed edge list, filtered to step <= t0;
    * `t0` and `room = 49 - t0`, both knowable at t0.

  For a NEIGHBOUR j at snapshot T, j's features are j's cumulative values over
  steps <= T -- also causal. Nothing in any arm reads a step > t0.

  VERIFIED EMPIRICALLY, not by assertion. `leakage_check` in the output:
    (a) LEAK CONTROL: an MLP on `t1 - t0`, the label's own source, must reach
        AUC ~ 1.0. If it does not, the pipeline cannot see the answer even when
        handed it, and the arms' results are uninterpretable.
    (b) SHUFFLED-LABEL control: train labels permuted, test AUC must be ~0.5.
    (c) FEATURE-FILTER verification: features recomputed for a sample of
        addresses straight from the raw CSVs under an explicit `step <= t0`
        filter, requiring exact agreement -- AND recomputed under a WRONG
        `step > t0` filter, which must DIFFER. Without the second half the first
        half would be vacuous if the filter were inert.
    (d) A NAMED-COLUMN denial: the model matrices are asserted to contain no
        column named among the lifetime quantities, and
        `wf["num_timesteps_appeared_in"] == n_steps_observed` is checked
        elementwise with the mismatch count reported.
    (e) A POSITIVE CONTROL on the per-address variance instrument itself: the
        same instrument is run on "Time step", which must vary within address
        for exactly the multi-step addresses (expected 1.0). A variance test
        that has never returned a nonzero reading has not been shown to be able
        to; the previous version of this check excluded "Time step" by name, so
        its empty `varying` list was true by construction.
=============================================================================

ARMS (all CPU; torch.set_num_threads(8) -- another job shares the box)
  1. feature-only MLP : own activity features at t0, no graph structure.
  2. GraphSAGE        : the same, plus graph structure at edges <= t0, plus a
                        2-layer SAGEConv embedding on the cumulative snapshot.
  3. TGN              : `torch_geometric.nn.models.tgn.TGNMemory`
                        (IdentityMessage + LastAggregator + GRUCell -- the
                        canonical PyG configuration) whose state at t0 is read
                        through a SAGEConv readout on the same snapshot graph
                        and concatenated with the arm-2 features.

  All three arms are MULTI-TASK models: one output head per Delta, sharing one
  trunk and one training run. The alternative -- one full run per Delta per arm
  -- spends 3x the compute to answer the same question, and the TGN memory pass
  (measured at 2.51 s per time step) does not depend on the label at all. The
  heads are the only per-Delta parameters and every arm gets the same treatment,
  so the comparison between arms is unchanged.

  The node set is ALL 822,942 addresses: an address's counterparties are
  informative whether or not they carry a label.

  Message passing uses the deduplicated (src, dst, step) edge set as an
  UNDIRECTED graph; the hand-built degree features keep edge MULTIPLICITY,
  because "how many transactions" is information while a repeated parallel edge
  adds nothing to a mean aggregation.

FEATURE DEFINITIONS (the ones that need saying)
  `c_distinct_out` / `c_distinct_in` are the CUMULATIVE SUM of the per-step
  distinct-counterparty counts, not the true distinct count over all steps <= t0.
  The true count is not available from a cumsum; the sum is, it is causal, and it
  is what the verification recomputes. Named here so the two are not confused.
  `c_tx_*_mean` are cumulative transaction-attribute means weighted by the
  per-step transaction count: a step with 40 transactions and a step with 1 do
  not carry equal weight.

METRICS
  AUC is the headline, per Delta. Accuracy is nearly uninformative: at Delta = 1
  ~92% of eligible addresses do not survive, so predicting "not present" for
  everyone already scores that, and the degenerate baseline's accuracy is printed
  beside every accuracy figure, for that Delta's eligible set. AUC carries a
  bootstrap CI (1000 resamples, fixed seed) and a class-stratified breakdown
  (illicit / licit / unknown). A within-t0 weighted AUC is reported too: `room`
  is knowable at t0 and is a strong predictor on its own, so a pooled AUC partly
  measures the calendar; the within-t0 version removes t0 exactly.

  Split by ADDRESS (never by row), 70/15/15, fixed seed, sizes in the output,
  cross-split overlap asserted zero.

  THE MODEL IS CLASS-BLIND. Class is never an input. Eligible survival rates
  differ strongly by class, so part of any well-fitting model's AUC is that
  class-correlated gap, recovered from behaviour rather than supplied.

USAGE
  python 53_E5p_temporal_gnn.py
  python 53_E5p_temporal_gnn.py --quick        # tiny, wiring check only
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score

BASE = "/root/cis/data/EllipticPlusPlus-main"
ACT = os.path.join(BASE, "Actors Dataset")
TXD = os.path.join(BASE, "Transactions Dataset")
OUT_JSON = "/root/cis/results/53_E5p_result.json"
OUT_TXT = "/root/cis/results/53_E5p_result.txt"

SEED_SPLIT = 20260924
SEED_TORCH = 20260925
SEED_BOOT = 20260926

N_STEPS_TOTAL = 49
DELTAS = [1, 3, 5]                        # pre-registered
DELTAS_CENSOR_TABLE = [1, 3, 5, 10, 20]   # reported so the trade-off is visible

TX_COLS = {"size": "size", "fees": "fees", "in_txs_degree": "in_deg",
           "out_txs_degree": "out_deg", "num_input_addresses": "n_in_addr",
           "num_output_addresses": "n_out_addr"}
COUNT_COLS = ["c_n_txs", "c_self_loops", "c_out_edges", "c_in_edges",
              "c_distinct_out", "c_distinct_in"]

# Columns of `wallets_features.csv` that are whole-lifetime quantities. Named
# explicitly so the denial is checkable rather than implied.
LIFETIME_COLUMNS_DENIED = [
    "num_timesteps_appeared_in", "first_block_appeared_in",
    "last_block_appeared_in", "lifetime_in_blocks", "total_txs",
    "transacted_w_address_total", "num_txs_as_sender", "num_txs_as receiver",
    "btc_transacted_total", "btc_sent_total", "btc_received_total",
    "fees_total", "blocks_btwn_txs_total", "num_addr_transacted_multiple",
]

FEAT_NAMES = [
    "t0", "room",
    "c_n_txs", "c_self_loops",
    "c_tx_size_mean", "c_tx_fees_mean",
    "c_tx_in_deg_mean", "c_tx_out_deg_mean",
    "c_tx_n_in_addr_mean", "c_tx_n_out_addr_mean",
    "c_out_edges", "c_in_edges",
    "c_distinct_out", "c_distinct_in",
]
CELL_FEATS = FEAT_NAMES[2:]
CELL_COLS = list(range(2, len(FEAT_NAMES)))
OWN_IDX = list(range(0, 10))
GRAPH_IDX = list(range(10, 14))
TAB_IDX = OWN_IDX + GRAPH_IDX
D_ALL = len(FEAT_NAMES)
D_OWN = len(OWN_IDX)
N_DELTA = len(DELTAS)
VERIFY_COLS = ["c_out_edges", "c_in_edges", "c_self_loops", "c_distinct_out",
               "c_distinct_in"]


# ===========================================================================
# Stage 0/1 -- the timed edge list and the causal per-(address, step) cells
# ===========================================================================
def build_cells(addr_index, quick=False):
    """One pass over the edge lists -> per-(address, step) counts, then their
    cumulative sums within address.

    "Cumulative" means `sum over steps <= s`, obtained by sorting on
    (address, step) and taking a within-address cumsum. That evaluates the
    `step <= T` filter for every T at once instead of once per T.
    """
    at = pd.read_csv(os.path.join(ACT, "AddrTx_edgelist.csv"))
    ta = pd.read_csv(os.path.join(ACT, "TxAddr_edgelist.csv"))
    txf = pd.read_csv(os.path.join(TXD, "txs_features.csv"),
                      usecols=["txId", "Time step"] + list(TX_COLS))
    if quick:
        at = at.iloc[:400000]
        ta = ta.iloc[:800000]
    at.columns = ["src", "txId"]
    ta.columns = ["txId", "dst"]

    e = at.merge(ta, on="txId", how="inner").merge(
        txf[["txId", "Time step"]], on="txId", how="inner")
    n_join = len(e)
    if n_join == 0:
        raise SystemExit("[53] EMPTY JOIN -- address->address construction failed")
    e["is_self"] = e["src"].values == e["dst"].values
    # map through float64 first: an unmapped string becomes NaN, which is
    # checkable; `.map` on a Series of strings with an int64 target silently
    # either raises or produces -1 depending on pandas' mood.
    e["src_idx"] = e["src"].map(addr_index).astype("float64")
    e["dst_idx"] = e["dst"].map(addr_index).astype("float64")
    if e["src_idx"].isna().any() or e["dst_idx"].isna().any():
        raise SystemExit("[53] an edge endpoint is not in wallets_classes")
    e["src_idx"] = e["src_idx"].astype("int64")
    e["dst_idx"] = e["dst_idx"].astype("int64")
    selfl = e[e["is_self"]]
    ee = e[~e["is_self"]].copy()
    del e

    cell_out = ee.groupby(["src_idx", "Time step"], sort=True).agg(
        out_edges=("dst_idx", "size"), distinct_out=("dst_idx", "nunique"))
    cell_in = ee.groupby(["dst_idx", "Time step"], sort=True).agg(
        in_edges=("src_idx", "size"), distinct_in=("src_idx", "nunique"))
    cell_self = selfl.groupby(["src_idx", "Time step"], sort=True).size()
    cell_self = cell_self.to_frame("self_loops")
    for d in (cell_out, cell_in, cell_self):
        d.index = d.index.set_names(["address", "step"])

    # transaction-level aggregates: one row per (address, txId) participation
    part = pd.concat([
        at.rename(columns={"src": "address"})[["address", "txId"]],
        ta.rename(columns={"dst": "address"})[["address", "txId"]],
    ], ignore_index=True).merge(txf, on="txId", how="inner")
    part["address"] = part["address"].map(addr_index).astype("float64")
    part = part.dropna(subset=["address"])
    part["address"] = part["address"].astype("int64")
    gb = part.groupby(["address", "Time step"], sort=True)
    cell_tx = gb.agg(n_txs=("txId", "nunique"))
    for raw, short in TX_COLS.items():
        cell_tx["m_" + short] = gb[raw].mean()
    cell_tx.index = cell_tx.index.set_names(["address", "step"])
    del part, gb

    cells = (cell_out.join(cell_in, how="outer")
             .join(cell_self, how="outer").join(cell_tx, how="outer")
             .fillna(0.0))
    del cell_out, cell_in, cell_self, cell_tx
    for c in ["out_edges", "in_edges", "distinct_out", "distinct_in",
              "self_loops", "n_txs"]:
        cells[c] = cells[c].astype("float32")
    cells = cells.reset_index()
    cells["address"] = cells["address"].astype("int64")
    cells["step"] = cells["step"].astype("int64")
    cells = cells.sort_values(["address", "step"],
                              kind="mergesort").reset_index(drop=True)

    for c in ["out_edges", "in_edges", "distinct_out", "distinct_in",
              "self_loops", "n_txs"]:
        cells["c_" + c] = cells.groupby("address", sort=False)[c].cumsum()
    # cumulative MEANS weighted by the per-step transaction count
    w = cells["n_txs"].values.astype("float64")
    aid = cells["address"].values
    cw = pd.Series(w).groupby(aid, sort=False).cumsum().values
    for short in TX_COLS.values():
        cs = (pd.Series(cells["m_" + short].values * w)
              .groupby(aid, sort=False).cumsum().values)
        cells["c_tx_" + short + "_mean"] = np.where(cw > 0,
                                                    cs / np.maximum(cw, 1e-9), 0.0)
    cells = cells.drop(columns=["m_" + s for s in TX_COLS.values()])

    meta = dict(n_join_rows=int(n_join), n_self_loop_rows=int(len(selfl)),
                n_edges=int(len(ee)), n_cells=int(len(cells)),
                step_min=int(cells["step"].min()) if len(cells) else None,
                step_max=int(cells["step"].max()) if len(cells) else None,
                distinct_out_definition=("cumulative SUM of per-step distinct "
                                         "counterparty counts"),
                quick=bool(quick))
    return ee, cells, meta


def transform_features(df):
    df = df.copy()
    for c in COUNT_COLS:
        df[c] = np.log1p(df[c].astype("float64"))
    for c in ["c_tx_size_mean", "c_tx_fees_mean"]:
        df[c] = np.log1p(np.clip(df[c].astype("float64"), 0, None))
    return df


# ===========================================================================
# Models -- all three carry one head per Delta (see the module docstring)
# ===========================================================================
class MLP(torch.nn.Module):
    def __init__(self, d_in, n_out, hidden=128, p=0.2):
        super().__init__()
        self.trunk = torch.nn.Sequential(
            torch.nn.Linear(d_in, hidden), torch.nn.ReLU(),
            torch.nn.Dropout(p),
            torch.nn.Linear(hidden, hidden // 2), torch.nn.ReLU())
        self.heads = torch.nn.Linear(hidden // 2, n_out)

    def forward(self, x):
        return self.heads(self.trunk(x))


class SageArm(torch.nn.Module):
    def __init__(self, d_node, d_tab, n_out, hidden=64, p=0.2):
        super().__init__()
        from torch_geometric.nn import SAGEConv
        self.conv1 = SAGEConv(d_node, hidden)
        self.conv2 = SAGEConv(hidden, hidden)
        self.p = p
        self.trunk = torch.nn.Sequential(
            torch.nn.Linear(hidden + d_tab, hidden), torch.nn.ReLU())
        self.heads = torch.nn.Linear(hidden, n_out)

    def embed(self, x, edge_index):
        h = F.relu(self.conv1(x, edge_index))
        h = F.dropout(h, p=self.p, training=self.training)
        return F.relu(self.conv2(h, edge_index))

    def readout(self, h_node, idx, tab):
        return self.heads(self.trunk(torch.cat([h_node[idx], tab], -1)))


class TGNArm(torch.nn.Module):
    """TGNMemory state at t0, read through a SAGEConv on the t0 snapshot.

    The message module is the canonical `IdentityMessage` -- a concat, so it has
    NO parameters of its own; the learnable state transition is the GRUCell plus
    `TimeEncoder`. (`msg_module.parameters()` is therefore empty, and asking it
    for a gradient raises `max() arg is an empty sequence`; that is how the first
    smoke test of this file failed. The gradient checks are written against gru /
    time_enc / head instead.) The SAGEConv readout is the "combine TGNMemory with
    SAGEConv/TransformerConv" of the plan.

    `tgn` is kept permanently in EVAL mode. In eval mode `update_state` stores
    the batch's messages and immediately applies them, so `tgn.memory` IS the
    state at steps <= T for every node and can be fed straight to the readout.
    (In train mode it applies whatever the PREVIOUS call stored and only then
    stores this call's, so the committed memory lags one batch and reading it
    needs a per-call `forward()` over the node set you hand it -- at 822,942
    nodes that is the whole cost of the arm, and it made the first smoke test run
    ~19 minutes without finishing. Measured in 53c: 2.51 s per time step in eval
    mode, with a gradient reaching the GRU and TimeEncoder on every step.)
    Switching a TGNMemory back from eval to train also triggers a full-node store
    flush, so nothing here ever calls `.train()` on the TGNMemory itself.
    """

    def __init__(self, num_nodes, d_tab, n_out, memory_dim=64, time_dim=16,
                 raw_dim=3, hidden=64):
        super().__init__()
        from torch_geometric.nn.models.tgn import (TGNMemory, IdentityMessage,
                                                   LastAggregator)
        from torch_geometric.nn import SAGEConv
        self.tgn = TGNMemory(
            num_nodes=num_nodes, raw_msg_dim=raw_dim, memory_dim=memory_dim,
            time_dim=time_dim,
            message_module=IdentityMessage(raw_dim, memory_dim, time_dim),
            aggregator_module=LastAggregator())
        self.conv = SAGEConv(memory_dim, hidden)
        self.trunk = torch.nn.Sequential(
            torch.nn.Linear(hidden + d_tab, hidden), torch.nn.ReLU())
        self.heads = torch.nn.Linear(hidden, n_out)
        with torch.no_grad():
            self.tgn.train(False)

    def set_train(self, mode):
        self.conv.train(mode)
        self.trunk.train(mode)

    def readout(self, idx, edge_index, tab):
        h = F.relu(self.conv(self.tgn.memory, edge_index))
        return self.heads(self.trunk(torch.cat([h[idx], tab], -1)))


# ===========================================================================
# Metrics
# ===========================================================================
def auc(y, s):
    y = np.asarray(y)
    if len(y) == 0 or y.min() == y.max():
        return None
    return float(roc_auc_score(y, s))


def bootstrap_auc(y, s, n=1000, seed=SEED_BOOT):
    """Bootstrap CI for AUC. 1000 resamples, fixed seed.

    A resample in which every draw has the same label has an undefined AUC; those
    are counted and reported (`n_skipped`) rather than silently scored 0.5.
    """
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    s = np.asarray(s, dtype="float64")
    k = len(y)
    vals, skipped = [], 0
    for _ in range(n):
        ii = rng.integers(0, k, k)
        yy = y[ii]
        if yy.min() == yy.max():
            skipped += 1
            continue
        vals.append(roc_auc_score(yy, s[ii]))
    if not vals:
        return dict(auc=auc(y, s), lo=None, hi=None, n_resamples=n, n_used=0,
                    n_skipped=skipped, seed=seed,
                    note="no resample contained both classes")
    vals = np.asarray(vals)
    return dict(auc=auc(y, s), lo=float(np.percentile(vals, 2.5)),
                hi=float(np.percentile(vals, 97.5)), n_resamples=n,
                n_used=int(len(vals)), n_skipped=int(skipped), seed=seed)


def within_t0_auc(t0, y, s):
    """AUC inside entry-step bins, pooled by bin size. `room` is knowable at t0
    and is a strong predictor on its own, so a pooled AUC partly measures the
    calendar; this removes t0 exactly."""
    t0 = np.asarray(t0)
    y = np.asarray(y)
    s = np.asarray(s, dtype="float64")
    parts, wts, per = [], [], {}
    for t in np.unique(t0):
        m = t0 == t
        a = auc(y[m], s[m])
        if a is None:
            continue
        parts.append(a)
        wts.append(int(m.sum()))
        per[int(t)] = [int(m.sum()), round(float(a), 5), int(y[m].sum()),
                       round(float(y[m].mean()), 5)]
    if not parts:
        return dict(weighted=None, unweighted=None, n_bins=0,
                    total_bins=int(len(np.unique(t0))), per_bin={})
    parts = np.asarray(parts)
    wts = np.asarray(wts, dtype="float64")
    return dict(weighted=float((parts * wts).sum() / wts.sum()),
                unweighted=float(parts.mean()), n_bins=int(len(parts)),
                total_bins=int(len(np.unique(t0))), per_bin=per)


def eval_block(y, s, t0, cls, light=False):
    """`light=True` skips the bootstrap. Used for the class-1/2 subset, whose
    members already carry bootstrapped numbers in `by_class`; bootstrapping both
    would double the most expensive part of the post-processing for no new
    information."""
    y = np.asarray(y)
    s = np.asarray(s, dtype="float64")
    n = len(y)
    out = dict(
        n=int(n), n_pos=int(y.sum()),
        pos_rate=float(y.mean()) if n else None,
        auc=(dict(auc=auc(y, s), lo=None, hi=None, note="light: no bootstrap")
             if light else bootstrap_auc(y, s)),
        auc_test=auc(y, s),
        accuracy_at_0p5=(float(((s >= 0.5).astype(int) == y).mean())
                         if n else None),
        degenerate_accuracy_predict_negative=float((1 - y).mean()) if n else None,
        avg_precision=(float(average_precision_score(y, s))
                       if 0 < y.sum() < n else None),
        score_mean=float(s.mean()) if n else None,
        within_t0_auc=within_t0_auc(t0, y, s))
    by_cls = {}
    for c, name in ((1, "illicit"), (2, "licit"), (3, "unknown")):
        m = np.asarray(cls) == c
        if m.sum() == 0:
            continue
        yy, ss = y[m], s[m]
        if light or not (0 < yy.sum() < m.sum()):
            by_cls[name] = dict(n=int(m.sum()), n_pos=int(yy.sum()),
                                pos_rate=float(yy.mean()),
                                auc=dict(auc=auc(yy, ss), lo=None, hi=None,
                                         note="no bootstrap (single-class or light)"))
        else:
            by_cls[name] = dict(n=int(m.sum()), n_pos=int(yy.sum()),
                                pos_rate=float(yy.mean()),
                                auc=bootstrap_auc(yy, ss))
    out["by_class"] = by_cls
    return out


# ===========================================================================
# Leakage helpers
# ===========================================================================
def to_native(o):
    """Recursively convert numpy scalars/arrays to Python natives.

    NOT `json.dump(..., default=str)`: that silently writes a string where a
    number was meant, and a downstream gate reading `arms.*.by_delta.*.auc_test`
    would then be comparing `"0.63"` -- a real way to break the driver's
    `ev_require` with no error appearing anywhere.
    """
    if isinstance(o, dict):
        return {str(k): to_native(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_native(v) for v in o]
    if isinstance(o, np.ndarray):
        return [to_native(v) for v in o.tolist()]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o


def wf_audit(wf):
    """Three questions answered on an already-loaded `wallets_features` frame.

    (i) Which columns vary within an address? (53a answered: none.)
    (ii) POSITIVE CONTROL: the same instrument run on "Time step", which must
         vary for every address observed at >= 2 steps.
    (iii) Is `num_timesteps_appeared_in` literally `n_steps_observed`?
    """
    cols = [c for c in wf.columns if c not in ("address", "Time step")]
    g = wf.groupby("address", sort=False)
    varying = [c for c in cols if bool((g[c].nunique(dropna=False) > 1).any())]
    nu_step = g["Time step"].nunique()
    multi = nu_step[nu_step >= 2].index
    pc = float((nu_step.loc[multi] > 1).mean()) if len(multi) else None
    claimed = g["num_timesteps_appeared_in"].max()
    j = pd.concat([claimed.rename("claimed"), nu_step.rename("observed")],
                  axis=1).dropna()
    mism = int((j["claimed"].astype(int) != j["observed"].astype(int)).sum())
    ex = None
    if mism:
        b = j[j["claimed"].astype(int) != j["observed"].astype(int)]
        ex = {str(k): [int(v["claimed"]), int(v["observed"])]
              for k, v in b.head(3).iterrows()}
    return dict(
        n_rows=int(len(wf)), n_columns_examined=len(cols),
        columns_constant_within_address=len(cols) - len(varying),
        columns_varying_within_address=len(varying), varying=varying,
        positive_control=dict(
            column="Time step",
            measured_on="the %d addresses with >= 2 observed steps" % len(multi),
            frac_multi_step_addresses_varying=pc,
            overall_frac_varying=round(float((nu_step > 1).mean()), 5),
            expectation="1.0 on multi-step addresses",
            note=("`Time step` is deliberately NOT excluded from the positive "
                  "control. The first version of this check excluded it by "
                  "name, which made `n_varying == 0` true by construction: the "
                  "instrument had never been shown able to return a nonzero "
                  "value, so its empty result proved nothing.")),
        label_identity=dict(
            column="num_timesteps_appeared_in", compared=int(len(j)),
            n_mismatch=mism, claim="equals n_steps_observed elementwise",
            examples=ex,
            note=("at Delta = 1 the label is 1[n_steps_observed >= 2], so this "
                  "column is the label in disguise. No arm uses it.")))


def _perstep_distinct(steps, counterparts):
    if len(steps) == 0:
        return 0.0
    df = pd.DataFrame({"s": np.asarray(steps), "c": np.asarray(counterparts)})
    return float(df.groupby("s")["c"].nunique().sum())


def verify_sample_features(pop, cell_raw, seed):
    """Recompute the cell features for a sample of addresses straight from the
    raw CSVs under an explicit `step <= t0` filter, compare with what the
    pipeline stored, then recompute under a deliberately WRONG `step > t0`
    filter -- which must DIFFER. If it agreed too, the filter would be inert and
    the first comparison would prove nothing.

    Grouped once into address -> row-index maps: filtering the 2.9M-row frame
    twice per sampled address would be ~1.7e9 row-ops, i.e. hours, and the first
    version of this function did exactly that.
    """
    rng = np.random.default_rng(seed)
    smp = np.sort(rng.choice(len(pop), size=min(300, len(pop)), replace=False))
    at = pd.read_csv(os.path.join(ACT, "AddrTx_edgelist.csv"))
    # ACT, not TXD. `TxAddr_edgelist.csv` is the tx->output_address mirror of
    # `AddrTx_edgelist.csv` (input_address->txId, read from ACT on the line
    # above); both edge lists ship in "Actors Dataset/". The Transactions
    # directory holds only `txs_features.csv` and `txs_edgelist.csv`. Joining
    # this filename with TXD raised FileNotFoundError at the end of the run --
    # after both arms had trained -- so the whole 49-minute run was lost to a
    # directory constant. (The `TXD and TXD` this replaced was a no-op: `X and X`
    # evaluates to X. Audited every os.path.join in this file afterwards; this
    # was the only wrong constant.)
    ta = pd.read_csv(os.path.join(ACT, "TxAddr_edgelist.csv"))
    txf = pd.read_csv(os.path.join(TXD, "txs_features.csv"),
                      usecols=["txId", "Time step"])
    at.columns = ["src", "txId"]
    ta.columns = ["txId", "dst"]
    e = at.merge(ta, on="txId", how="inner").merge(txf, on="txId", how="inner")
    e = e[e["src"].values != e["dst"].values].reset_index(drop=True)
    i_src = e.groupby("src", sort=False).indices
    i_dst = e.groupby("dst", sort=False).indices
    srcv, dstv, stepv = e["src"].values, e["dst"].values, e["Time step"].values
    del at, ta, txf, e

    cols = [CELL_FEATS.index(c) for c in VERIFY_COLS]
    addrs = pop.index.values[smp]
    t0s = pop["t0"].values[smp]
    stored = cell_raw[smp][:, cols].astype(float)

    n_exact = n_diff_gt = 0
    bad = []
    for i, (a, t0) in enumerate(zip(addrs, t0s)):
        r = np.union1d(i_src.get(a, np.empty(0, dtype="int64")),
                       i_dst.get(a, np.empty(0, dtype="int64")))
        if len(r) == 0:
            continue
        ss, dd, tt = srcv[r], dstv[r], stepv[r]
        for le in (True, False):
            m = tt <= t0 if le else tt > t0
            s2, d2, t2 = ss[m], dd[m], tt[m]
            is_src, is_dst = s2 == a, d2 == a
            vals = np.zeros(len(VERIFY_COLS))
            vals[0] = is_src.sum()
            vals[1] = is_dst.sum()
            # a self-loop has src == dst == a, so it is in both
            vals[2] = int((is_src & is_dst).sum())
            vals[3] = _perstep_distinct(t2[is_src], d2[is_src])
            vals[4] = _perstep_distinct(t2[is_dst], s2[is_dst])
            if le:
                if np.allclose(stored[i], vals, atol=1e-6):
                    n_exact += 1
                elif len(bad) < 5:
                    bad.append(dict(address=str(a), t0=int(t0),
                                    stored=[round(float(v), 4) for v in stored[i]],
                                    recomputed=[float(v) for v in vals]))
            elif not np.array_equal(stored[i], vals):
                n_diff_gt += 1
    n = len(addrs)
    return dict(n_sampled=int(n), n_compared=int(n), n_exact_match=int(n_exact),
                n_mismatch=int(n - n_exact), features_compared=VERIFY_COLS,
                n_where_leq_differs_from_gt=int(n_diff_gt),
                frac_where_leq_differs_from_gt=round(n_diff_gt / max(n, 1), 4),
                first_mismatches=bad,
                note=("recomputed from the raw AddrTx/TxAddr/txs_features CSVs. "
                      "`leq` counts edges with step <= t0 and must equal what "
                      "the pipeline stored; `gt` counts edges with step > t0 and "
                      "must DIFFER, otherwise the filter is inert and the "
                      "equality above would prove nothing."))


# ===========================================================================
# Main
# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--mlp-epochs", type=int, default=20)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--eval-every", type=int, default=2,
                    help="snapshot arms evaluate on val every N epochs")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    if args.quick:
        args.epochs, args.mlp_epochs = 2, 3

    torch.set_num_threads(8)
    t_start = time.time()
    r = {"meta": {
        "script": "53_E5p_temporal_gnn.py",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "epochs_snapshot_arms": args.epochs, "epochs_mlp": args.mlp_epochs,
        "hidden": args.hidden, "eval_every": args.eval_every,
        "quick": bool(args.quick), "threads": 8,
        "seeds": {"split": SEED_SPLIT, "torch": SEED_TORCH,
                  "bootstrap": SEED_BOOT},
        "n_steps_total": N_STEPS_TOTAL,
        "deltas": DELTAS,
        "deltas_censoring_table": DELTAS_CENSOR_TABLE,
        "delta_preregistration": (
            "Delta is unspecified by the plan. Pre-registered set {1,3,5}: "
            "Delta=1 is the plan's degenerate end and equals E5-fin's "
            "recurrence label; 3 and 5 keep censoring under ~12% on the "
            "labelled cohort. All three are reported; the censoring table "
            "extends to 10 and 20 so the trade-off is visible."),
        "label": ("label_D = 1[ t1 - t0 >= D ], t0/t1 the first/last observed "
                  "step; eligible only if t0 <= 49 - D"),
        "feature_names": FEAT_NAMES,
        "arm1_feature_names": [FEAT_NAMES[i] for i in OWN_IDX],
        "graph_feature_names": [FEAT_NAMES[i] for i in GRAPH_IDX],
        "population": "all 822,942 addresses with >= 1 observed step",
        "class_blind": True,
        "multi_task_note": ("one output head per Delta per arm, sharing one "
                            "trunk and a single training run; all arms treated "
                            "identically")}}
    torch.manual_seed(SEED_TORCH)
    np.random.seed(SEED_TORCH)

    def log(*a):
        print("[53 %.1fs]" % (time.time() - t_start), *a, flush=True)

    # ---- addresses, t0/t1, labels -----------------------------------------
    wc = pd.read_csv(os.path.join(ACT, "wallets_classes.csv"))
    wc.columns = ["address", "class"]
    addr_index = pd.Series(np.arange(len(wc), dtype="int64"),
                           index=wc["address"].values)
    n_nodes = len(wc)

    # ONE read of the 606 MB file. It is used for four things: t0/t1/nsteps, the
    # column-variance audit, the `num_timesteps_appeared_in` identity check, and
    # the INADMISSIBLE naive baseline below.
    wf = pd.read_csv(os.path.join(ACT, "wallets_features.csv"))
    ag = wf.groupby("address", sort=False)["Time step"]
    t0_min_all = ag.min()                    # every address in the file
    pop = pd.concat([t0_min_all.rename("t0"), ag.max().rename("t1"),
                     ag.nunique().rename("n_steps_observed")], axis=1)
    del ag
    pop = pop[pop.index.isin(addr_index.index)].join(
        wc.set_index("address")[["class"]], how="left")
    pop["t0"] = pop["t0"].astype(int)
    pop["t1"] = pop["t1"].astype(int)
    if args.quick:
        pop = pop.iloc[:30000].copy()
    n_pop = int(len(pop))
    r["population"] = dict(
        n_addresses_in_classes=int(len(wc)), n_with_at_least_one_step=n_pop,
        n_dropped_no_step=int(len(wc) - n_pop),
        by_class={str(c): int(v) for c, v in
                  pop["class"].value_counts().sort_index().items()})
    log("population", r["population"])

    # ---- the plan's MLP baseline AS SPECIFIED, i.e. built from the provided
    # table. Every one of these columns is constant within address, so `.first()`
    # is the address-level value and no information is lost by it. THIS IS THE
    # LEAK, MEASURED RATHER THAN ASSERTED: it is reported, per Delta, in
    # `naive_leaking_baseline`, and it is NOT admissible as a baseline.
    naive_cols = [c for c in wf.columns if c not in ("address", "Time step")]
    naive_all = wf.groupby("address", sort=False)[naive_cols].first()
    NAIVE = naive_all.reindex(pop.index).fillna(0.0).values.astype("float64")
    del naive_all
    r["naive_baseline_columns"] = list(naive_cols)
    log("naive provided-column matrix", NAIVE.shape)

    wa = wf_audit(wf.head(200000) if args.quick else wf)
    del wf

    # ---- censoring table (computed here, not quoted from anywhere) --------
    cens = {}
    cls_raw = pop["class"].values
    for D in DELTAS_CENSOR_TABLE:
        elig = (pop["t0"].values + D) <= N_STEPS_TOTAL
        pos = (pop["t1"].values - pop["t0"].values) >= D
        ent = dict(delta=D, eligible=int(elig.sum()),
                   excluded_censored=int((~elig).sum()),
                   excluded_share=round(float((~elig).mean()), 5),
                   n_pos=int(pos[elig].sum()),
                   pos_rate_eligible=round(float(pos[elig].mean()), 5))
        for c, nm in ((1, "illicit"), (2, "licit"), (3, "unknown")):
            mc = cls_raw == c
            e2 = elig & mc
            ent[nm] = dict(
                n=int(mc.sum()), eligible=int(e2.sum()),
                excluded_share=round(float((~elig[mc]).mean()), 5),
                n_pos=int(pos[e2].sum()),
                pos_rate=round(float(pos[e2].mean()), 5) if e2.sum() else None)
        lab = np.isin(cls_raw, [1, 2])
        ent["cohort_class12"] = dict(
            n=int(lab.sum()), eligible=int((elig & lab).sum()),
            excluded_share=round(float((~elig[lab]).mean()), 5),
            n_pos=int(pos[elig & lab].sum()),
            pos_rate=(round(float(pos[elig & lab].mean()), 5)
                      if (elig & lab).sum() else None))
        cens[str(D)] = ent
    r["censoring"] = cens
    r["censoring_note"] = (
        "`excluded_censored` = addresses with t0 > 49 - D, for which the label "
        "cannot be satisfied inside the window. They are EXCLUDED from that "
        "Delta's eligible set, never relabelled 0.")
    log("censoring", {k: [v["excluded_share"], v["pos_rate_eligible"]]
                      for k, v in cens.items()})

    t0hist = pop["t0"].value_counts().sort_index()
    r["t0_structural_zero"] = dict(
        t0_49_n=int(t0hist.get(49, 0)),
        t0_45_to_48_n=int(sum(int(t0hist.get(t, 0)) for t in (45, 46, 47, 48))),
        note=("an address first seen at t0 can satisfy t1 - t0 >= D only if "
              "t0 <= 49 - D. At t0 = 49 the D = 1 label is a structural zero, "
              "not a low rate; at D = 5 it is a structural zero for all "
              "t0 >= 45. Any statement that persistence 'falls with Delta' "
              "partly restates this window effect."))

    # ---- labels, eligibility ---------------------------------------------
    t0v = pop["t0"].values.astype("float64")
    ratev = (pop["t1"].values - pop["t0"].values).astype("float64")
    nstv = pop["n_steps_observed"].values.astype("float64")
    Y = np.zeros((n_pop, N_DELTA), dtype="float32")
    OK = np.zeros((n_pop, N_DELTA), dtype=bool)
    for k, D in enumerate(DELTAS):
        OK[:, k] = (t0v + D) <= N_STEPS_TOTAL
        Y[:, k] = ((ratev >= D) & OK[:, k]).astype("float32")
    r["label_prevalence_eligible"] = {
        str(D): round(float(Y[OK[:, k], k].mean()), 5)
        for k, D in enumerate(DELTAS)}
    r["label_prevalence_by_class"] = {}
    for c, nm in ((1, "illicit"), (2, "licit"), (3, "unknown")):
        mc = cls_raw == c
        r["label_prevalence_by_class"][nm] = {
            str(D): (round(float(Y[mc & OK[:, k], k].mean()), 5)
                     if (mc & OK[:, k]).sum() else None)
            for k, D in enumerate(DELTAS)}
    # D = 1 must reproduce E5-fin's recurrence count exactly
    r["delta1_equals_recurrence"] = dict(
        n_delta1_pos=int(Y[:, 0].sum()), n_nsteps_ge_2=int((nstv >= 2).sum()),
        identical=bool(int(Y[:, 0].sum()) == int((nstv >= 2).sum())),
        note="label_D at D = 1 is 1[t1 > t0], i.e. 1[n_steps_observed >= 2]")

    # ---- split by address -------------------------------------------------
    rng = np.random.default_rng(SEED_SPLIT)
    perm = rng.permutation(n_pop)
    n_tr = int(0.70 * n_pop)
    n_va = int(0.15 * n_pop)
    split = np.array(["test"] * n_pop, dtype=object)
    split[perm[:n_tr]] = "train"
    split[perm[n_tr:n_tr + n_va]] = "val"
    tr_m, va_m, te_m = split == "train", split == "val", split == "test"
    is12 = np.isin(cls_raw, [1, 2])
    r["split"] = dict(
        by="address", seed=SEED_SPLIT, train=int(tr_m.sum()),
        val=int(va_m.sum()), test=int(te_m.sum()),
        train_class12=int((tr_m & is12).sum()),
        test_only_class12=int((te_m & is12).sum()),
        overlap_train_val=int(len(np.intersect1d(np.where(tr_m)[0],
                                                 np.where(va_m)[0]))),
        overlap_train_test=int(len(np.intersect1d(np.where(tr_m)[0],
                                                  np.where(te_m)[0]))),
        overlap_val_test=int(len(np.intersect1d(np.where(va_m)[0],
                                                np.where(te_m)[0]))))
    log("split", r["split"])

    # ---- causal feature matrix (one row: one address at its t0) ----------
    ee, cells, edge_meta = build_cells(addr_index, quick=args.quick)
    r["edges"] = edge_meta
    log("edges", edge_meta)

    cm = cells.set_index(["address", "step"])
    key = pd.MultiIndex.from_arrays([
        pop.index.map(addr_index).values.astype("int64"),
        t0v.astype("int64")])
    tgt = cm.reindex(key)
    r["population_missing_cell"] = int(tgt["c_n_txs"].isna().sum())
    cell_raw = tgt[CELL_FEATS].fillna(0.0).reset_index(drop=True).values.astype("float64")
    Xcell = transform_features(
        pd.DataFrame(cell_raw, columns=CELL_FEATS)).values.astype("float64")
    Xall = np.concatenate([t0v.reshape(-1, 1),
                           (N_STEPS_TOTAL - t0v).reshape(-1, 1), Xcell],
                          axis=1).astype("float64")
    assert Xall.shape[1] == D_ALL, (Xall.shape, D_ALL)
    r["feature_matrix"] = dict(
        shape=list(Xall.shape), columns=FEAT_NAMES,
        source=("rebuilt from the timed edge stream truncated at t0; no column "
                "of wallets_features is used as a feature"))

    # (d) named-column denial
    denied = [c for c in FEAT_NAMES if c in LIFETIME_COLUMNS_DENIED]
    assert not denied, "lifetime column leaked into the feature matrix: %s" % denied
    assert "num_timesteps_appeared_in" not in FEAT_NAMES

    mu = Xall[tr_m].mean(0)
    sd = Xall[tr_m].std(0)
    sd[sd < 1e-8] = 1.0
    r["standardisation"] = dict(
        fit_on="train-split rows only", clip=[-8, 8],
        mean=[round(float(v), 6) for v in mu],
        std=[round(float(v), 6) for v in sd])

    def std(a, cols=None):
        m = mu if cols is None else mu[cols]
        s = sd if cols is None else sd[cols]
        return np.clip((np.asarray(a, dtype="float64") - m) / s,
                       -8.0, 8.0).astype("float32")

    X = std(Xall)
    tab_all = torch.from_numpy(np.ascontiguousarray(X))
    Yt = torch.from_numpy(Y)
    OKt = torch.from_numpy(OK)
    tr_np = tr_m
    pos_w = np.array([((OK[:, k] & tr_m & (Y[:, k] == 0)).sum())
                      / max((OK[:, k] & tr_m & (Y[:, k] == 1)).sum(), 1)
                      for k in range(N_DELTA)], dtype="float32")
    r["pos_weight_train"] = [float(v) for v in pos_w]
    pos_wt = torch.from_numpy(pos_w)

    # node-level t0 for the snapshot readout's constants (reindexed once)
    t0_all = t0_min_all.reindex(wc["address"].values).fillna(0).values.astype("float64")
    const_block = std(np.stack([t0_all, N_STEPS_TOTAL - t0_all], axis=1),
                      cols=[0, 1])
    node_of_pop = pop.index.map(addr_index).values.astype("int64")

    # ---- snapshot graph ---------------------------------------------------
    edup = ee.drop_duplicates(subset=["src_idx", "dst_idx", "Time step"])
    r["graph"] = dict(
        n_edges_with_multiplicity=int(len(ee)),
        n_distinct_src_dst_step=int(len(edup)),
        dedup_shrink=round(1 - len(edup) / max(len(ee), 1), 4),
        n_nodes_in_graph=int(pd.unique(np.concatenate(
            [edup["src_idx"].values, edup["dst_idx"].values])).size),
        note=("dedup affects message passing only; degree features keep edge "
              "multiplicity"))
    src = edup["src_idx"].values.astype("int64")
    dst = edup["dst_idx"].values.astype("int64")
    step = edup["Time step"].values.astype("int64")
    ei = np.concatenate([np.stack([src, dst]), np.stack([dst, src])], axis=1)
    st = np.concatenate([step, step])
    order = np.argsort(st, kind="mergesort")
    ei = torch.from_numpy(np.ascontiguousarray(ei[:, order]))
    st = st[order]
    cum_edges = np.cumsum(np.bincount(st, minlength=N_STEPS_TOTAL + 2))
    r["graph"]["undirected_distinct_edges"] = int(ei.shape[1])
    log("graph", r["graph"]["undirected_distinct_edges"], "undirected edges")

    # ---- per-step node feature updates -----------------------------------
    step_arr = cells["step"].values
    addr_arr = cells["address"].values.astype("int64")
    cell_mat = cells[CELL_FEATS].values.astype("float64")
    upd_idx, upd_vals = [], []
    for t in range(1, N_STEPS_TOTAL + 1):
        ix = np.where(step_arr == t)[0]
        upd_idx.append(torch.from_numpy(addr_arr[ix]))
        upd_vals.append(torch.from_numpy(
            std(transform_features(pd.DataFrame(cell_mat[ix],
                                                columns=CELL_FEATS)).values,
                cols=CELL_COLS)))
    sel_by_step = {t: np.where(t0v == t)[0] for t in range(1, N_STEPS_TOTAL + 1)}
    r["node_feature_updates"] = dict(
        n_cells=int(len(cells)),
        max_rows_in_one_step=int(max(len(i) for i in upd_idx)),
        mean_rows_in_one_step=round(float(np.mean([len(i) for i in upd_idx])), 1))

    # ---- TGN events -------------------------------------------------------
    txm = pd.read_csv(os.path.join(TXD, "txs_features.csv"),
                      usecols=["txId"] + list(TX_COLS))
    raw = edup[["txId"]].merge(txm, on="txId", how="left")
    rmb = np.stack([
        np.log1p(raw["num_input_addresses"].values.astype("float64")),
        np.log1p(raw["num_output_addresses"].values.astype("float64")),
        np.log1p(np.clip(raw["size"].values.astype("float64"), 0, None))],
        axis=1)
    rmb = np.nan_to_num(rmb, nan=0.0, posinf=0.0, neginf=0.0)
    rmb = (rmb - rmb.mean(0)) / (rmb.std(0) + 1e-9)
    ev_raw_all = torch.from_numpy(np.ascontiguousarray(rmb.astype("float32")))
    del raw, txm, rmb
    ev_ix = [np.where(step == t)[0] for t in range(1, N_STEPS_TOTAL + 1)]
    ev_src = [torch.from_numpy(src[i]) for i in ev_ix]
    ev_dst = [torch.from_numpy(dst[i]) for i in ev_ix]
    ev_raw = [ev_raw_all[i] for i in ev_ix]
    # `t` must be LONG: TGNMemory scatters it into its long `last_update` buffer,
    # and a float `t` raises "Index put requires the source and destination
    # dtypes match, got Long for the destination and Float for the source". The
    # error names dtypes, not the argument.
    ev_t = [torch.full((len(i),), t, dtype=torch.long)
            for t, i in enumerate(ev_ix, start=1)]
    r["tgn_raw_message"] = dict(
        dim=3, columns=["log1p(num_input_addresses)",
                        "log1p(num_output_addresses)", "log1p(size)"],
        standardised=True, n_events=int(len(edup)),
        events_per_step_mean=round(len(edup) / float(N_STEPS_TOTAL), 1))
    del ev_raw_all

    # ================= ARM 1: feature-only MLP =============================
    def run_mlp(d_in, feats, tag, epochs, shuffle_train_labels=False):
        torch.manual_seed(SEED_TORCH)
        net = MLP(d_in, N_DELTA, hidden=128)
        opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-5)
        ytr = Y.copy()
        # `ysel` holds the labels used for CHECKPOINT SELECTION only. For a
        # normal arm it IS `Y` (same object, no copy) so selection is exactly
        # what it always was. For the shuffled control it must NOT be `Y`: the
        # first version shuffled the TRAINING labels and then selected the
        # checkpoint by TRUE validation-label AUC, which is the one thing a
        # label-permutation control has to be blind to. A model chosen by the
        # answer it is supposed to be unable to see cannot sit at chance -- and
        # more epochs give it more chances to be chosen, which is why the
        # control's val AUC rose monotonically (0.79579 -> 0.83927) while its
        # training labels were pure noise. Shuffling the selection labels too is
        # the exact analogue of what an arm does (select on the labels it was
        # trained on), so the two remain comparable.
        ysel = Y
        if shuffle_train_labels:
            rs = np.random.default_rng(SEED_SPLIT + 7)
            for k in range(N_DELTA):
                col = ytr[:, k].copy()
                col[tr_np] = rs.permutation(col[tr_np])
                ytr[:, k] = col
            ysel = Y.copy()
            for k in range(N_DELTA):
                col = ysel[:, k].copy()
                col[va_m] = rs.permutation(col[va_m])
                ysel[:, k] = col
        xt = torch.from_numpy(np.ascontiguousarray(feats))
        yt = torch.from_numpy(ytr)
        rngb = np.random.default_rng(SEED_TORCH)
        net.train()
        best, best_state, hist = -1.0, None, []
        for ep in range(epochs):
            o = rngb.permutation(len(xt))
            for i in range(0, len(o), 4096):
                b = o[i:i + 4096]
                out = net(xt[b])
                loss = torch.zeros(())
                for k in range(N_DELTA):
                    mk = OKt[b, k]
                    if int(mk.sum()) == 0:
                        continue
                    loss = loss + F.binary_cross_entropy_with_logits(
                        out[mk, k], yt[b][mk, k], pos_weight=pos_wt[k])
                if not loss.requires_grad:
                    continue
                opt.zero_grad()
                loss.backward()
                opt.step()
            with torch.no_grad():
                pv = torch.sigmoid(net(xt)).numpy()
            # Reported history always uses the TRUE validation labels -- that is
            # the measurement, and for the shuffled control it is the evidence
            # that the control was learning something it should not have been
            # able to. Selection uses `ysel`, which equals Y for an arm and is
            # itself shuffled for the control.
            a = float(np.mean([
                auc(Y[va_m & OK[:, k], k], pv[va_m & OK[:, k], k]) or 0.0
                for k in range(N_DELTA)]))
            a_sel = a if not shuffle_train_labels else float(np.mean([
                auc(ysel[va_m & OK[:, k], k], pv[va_m & OK[:, k], k]) or 0.0
                for k in range(N_DELTA)]))
            hist.append({"epoch": ep + 1, "val_auc_mean": round(a, 5),
                         "selection_auc": round(a_sel, 5)})
            if a_sel > best:
                best = a_sel
                best_state = {k: v.clone() for k, v in net.state_dict().items()}
            log("  %s ep%d val_auc_mean %.5f" % (tag, ep + 1, a))
        if best_state is not None:
            net.load_state_dict(best_state)
        net.eval()
        with torch.no_grad():
            sc = torch.sigmoid(net(xt)).numpy()
        return dict(val_auc_mean=best, history=hist, scores=sc,
                    n_params=int(sum(p.numel() for p in net.parameters())))

    results = {}
    t_arm = time.time()
    arm1 = run_mlp(D_OWN, X[:, OWN_IDX], "mlp", args.mlp_epochs)
    results["mlp_feature_only"] = dict(
        features="own activity at step <= t0 only (no graph structure)",
        feature_names=[FEAT_NAMES[i] for i in OWN_IDX], graph="none",
        val_auc_mean=arm1["val_auc_mean"], n_params=arm1["n_params"],
        history=arm1["history"], epochs=args.mlp_epochs,
        seconds=round(time.time() - t_arm, 1), by_delta={})
    log("ARM mlp done")

    # ---- the plan's MLP baseline AS SPECIFIED: built from the provided table,
    # on every one of its %d columns. Reported because the plan names "MLP 特征
    # 基线", and this measures what that baseline would have been.
    # INADMISSIBLE -- it reads the answer. See `naive_leaking_baseline.note`.
    Nmu = NAIVE[tr_m].mean(0)
    Nsd = NAIVE[tr_m].std(0)
    Nsd[Nsd < 1e-8] = 1.0
    NX = np.clip((NAIVE - Nmu) / Nsd, -8.0, 8.0).astype("float32")
    t_naive = time.time()
    naive = run_mlp(len(naive_cols), NX, "naive", max(args.mlp_epochs // 2, 8))
    nv = {"features": "all %d non-key, non-time columns of the provided "
                      "wallets_features.csv (address-level lifetime aggregates)"
          % len(naive_cols),
          "feature_columns": list(naive_cols), "n_params": naive["n_params"],
          "val_auc_mean": naive["val_auc_mean"], "history": naive["history"],
          "epochs": max(args.mlp_epochs // 2, 8),
          "seconds": round(time.time() - t_naive, 1),
          "admissible": False,
          "admissibility": (
              "INADMISSIBLE. Not a baseline -- a measurement of the leak. Every "
              "one of these columns is computed over the address's whole "
              "lifetime, i.e. over steps after t0, so the model is handed the "
              "answer. At Delta = 1 the label is literally "
              "1[num_timesteps_appeared_in >= 2] and that column is in this "
              "matrix."),
          "note": (
              "The plan names an 'MLP 特征基线'. Built the plan's way -- from "
              "the provided table -- it is this. The plan's own risk table fires "
              "a fallback ('降级为 GraphSAGE + 手工时序特征') when the temporal "
              "GNN improves little over the baseline; against this baseline "
              "every honest arm would look weak, so the fallback would fire on "
              "an artefact of the baseline rather than on a property of the "
              "GNN. That is why `mlp_feature_only` above is rebuilt from the "
              "edge stream truncated at t0 instead."),
          "by_delta": {}}
    for k, D in enumerate(DELTAS):
        base = te_m & OK[:, k]
        nv["by_delta"][str(D)] = eval_block(
            Y[base, k], naive["scores"][base, k], t0v[base], cls_raw[base])
    r["naive_leaking_baseline"] = nv
    log("naive baseline", {D: round(nv["by_delta"][D]["auc_test"], 4)
                           for D in map(str, DELTAS)})
    del NAIVE, NX, naive

    # ================= snapshot arms (2 and 3) =============================
    def y_of_sel(sel, mk, k):
        return Yt[torch.from_numpy(sel[mk.numpy()]), k]

    def snapshot_pass(net, opt, kind, train):
        if kind == "tgn":
            net.set_train(train)
            with torch.no_grad():
                net.tgn.reset_state()
        else:
            net.train(train)
        preds = torch.zeros((n_pop, N_DELTA), dtype=torch.float32)
        x = torch.zeros((n_nodes, D_ALL), dtype=torch.float32)
        x[:, 0:2] = torch.from_numpy(const_block)
        tl, nb = 0.0, 0
        for T in range(1, N_STEPS_TOTAL + 1):
            x[upd_idx[T - 1], 2:] = upd_vals[T - 1]
            eiT = ei[:, :cum_edges[T]]
            sel = sel_by_step[T]
            if kind == "tgn":
                net.tgn.update_state(ev_src[T - 1], ev_dst[T - 1],
                                     ev_t[T - 1], ev_raw[T - 1])
            if len(sel) == 0:
                if kind == "tgn":
                    net.tgn.detach()
                continue
            sel_i = torch.from_numpy(node_of_pop[sel])
            if kind == "tgn":
                logit = net.readout(sel_i, eiT, tab_all[sel_i])
            else:
                logit = net.readout(net.embed(x, eiT), sel_i, tab_all[sel_i])
            preds[sel] = torch.sigmoid(logit.detach())
            if train:
                m = OKt[sel] & torch.from_numpy(tr_m[sel]).reshape(-1, 1)
                loss = torch.zeros(())
                for k in range(N_DELTA):
                    mk = m[:, k]
                    if int(mk.sum()) == 0:
                        continue
                    loss = loss + F.binary_cross_entropy_with_logits(
                        logit[mk, k], y_of_sel(sel, mk, k), pos_weight=pos_wt[k])
                if loss.requires_grad:
                    opt.zero_grad()
                    loss.backward()
                    opt.step()
                    tl += float(loss)
                    nb += 1
            if kind == "tgn":
                net.tgn.detach()
        return preds, tl / max(nb, 1)

    def val_auc_of(p):
        pn = p.numpy()
        return float(np.mean([
            auc(Y[va_m & OK[:, k], k], pn[va_m & OK[:, k], k]) or 0.0
            for k in range(N_DELTA)]))

    def train_snapshot_arm(kind, epochs, eval_every):
        torch.manual_seed(SEED_TORCH)
        if kind == "tgn":
            net = TGNArm(n_nodes, len(TAB_IDX), N_DELTA, hidden=args.hidden)
        else:
            net = SageArm(D_ALL, len(TAB_IDX), N_DELTA, hidden=args.hidden)
        opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-5)
        best, best_state, hist = -1.0, None, []
        for ep in range(epochs):
            t_ep = time.time()
            _, tl = snapshot_pass(net, opt, kind, True)
            a = None
            if (ep + 1) % eval_every == 0 or ep == epochs - 1:
                with torch.no_grad():
                    p, _ = snapshot_pass(net, opt, kind, False)
                a = val_auc_of(p)
                if a > best:
                    best = a
                    best_state = {k: v.clone() for k, v in net.state_dict().items()}
            hist.append({"epoch": ep + 1, "train_loss": round(tl, 5),
                         "val_auc_mean": None if a is None else round(a, 5),
                         "seconds": round(time.time() - t_ep, 1)})
            log("  %s ep%d loss %.4f val %s (%.0fs)"
                % (kind, ep + 1, tl, a, time.time() - t_ep))
        if best_state is not None:
            net.load_state_dict(best_state)
        with torch.no_grad():
            p, _ = snapshot_pass(net, opt, kind, False)
        extra = {}
        if kind == "tgn":
            with torch.no_grad():
                extra = {"memory_absmean_end": float(net.tgn.memory.abs().mean()),
                         "memory_changed":
                             bool(float(net.tgn.memory.abs().sum()) > 0)}
        return dict(val_auc_mean=best, history=hist, scores=p.numpy(),
                    n_params=int(sum(q.numel() for q in net.parameters())),
                    **extra)

    for kind, key, feats, gdesc in (
            ("sage", "graphsage",
             "own features + graph structure (edges <= t0) + a 2-layer SAGEConv "
             "embedding on the cumulative snapshot graph",
             "undirected deduplicated timed address->address edges, cumulative "
             "snapshot per step; all 822,942 addresses are nodes"),
            ("tgn", "tgn",
             "TGNMemory state at t0 (IdentityMessage + LastAggregator + GRUCell) "
             "through a SAGEConv readout on the t0 snapshot graph, concatenated "
             "with the arm-2 tabular features",
             "same snapshot graph as the GraphSAGE arm; TGN events are the same "
             "deduplicated (src, dst, step) stream")):
        t_arm = time.time()
        arm = train_snapshot_arm(kind, args.epochs, args.eval_every)
        results[key] = dict(
            features=feats, feature_names=[FEAT_NAMES[i] for i in TAB_IDX],
            graph=gdesc, val_auc_mean=arm["val_auc_mean"],
            n_params=arm["n_params"], history=arm["history"],
            epochs=args.epochs, seconds=round(time.time() - t_arm, 1),
            by_delta={}, **{k: v for k, v in arm.items()
                            if k.startswith("memory_")})
        results[key]["_scores"] = arm["scores"]
        log("ARM %s done" % kind)

    for name in list(results.keys()):
        a = results[name]
        sc = (arm1["scores"] if name == "mlp_feature_only" else a.pop("_scores"))
        for k, D in enumerate(DELTAS):
            base = te_m & OK[:, k]
            blk = eval_block(Y[base, k], sc[base, k], t0v[base], cls_raw[base])
            sub = base & is12
            blk["class12_subset"] = eval_block(
                Y[sub, k], sc[sub, k], t0v[sub], cls_raw[sub], light=True)
            blk["class12_subset_note"] = (
                "predictions of the SAME model restricted to the labelled "
                "cohort; no separate model was trained on it "
                "(E5-fin-comparable)")
            a["by_delta"][str(D)] = blk
        a["score_convention"] = ("test metrics use the eligible test set "
                                 "te_m & OK[:, k] for each Delta")
    r["arms"] = results
    log("arms assembled")

    # ================= leakage checks ======================================
    lc = {}
    t_lc = time.time()

    def wtauc(mask, k, scores):
        """Within-entry-step AUC for a control -- the same `within_t0_auc` the
        arms already report through `eval_block`.

        The controls were the only objects in this script still reporting a
        POOLED AUC, and `within_t0_auc`'s own docstring says why that matters:
        "`room` is knowable at t0 and is a strong predictor on its own, so a
        pooled AUC partly measures the calendar". So the control's headline
        number and the arms' headline number were NOT the same quantity, and the
        ~0.5 "chance" band was being applied to the confounded one. A scorer that
        merely ranks by entry step -- learnable from features with no labels at
        all -- scores above 0.5 pooled, which is a floor of the METRIC, not
        evidence about the model.
        """
        m = mask & OK[:, k]
        return within_t0_auc(t0v[m], Y[m, k], scores[m])

    def wt_vals(blk):
        """The weighted within-t0 values, or None where a delta is missing."""
        out = []
        for D in DELTAS:
            e = blk.get(str(D)) or {}
            v = e.get("weighted")
            out.append(v if numlike(v) else None)
        return out

    def numlike(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    lk = run_mlp(1, ratev.reshape(-1, 1).astype("float32"), "leakctl",
                 max(args.mlp_epochs // 2, 8))
    lc["leak_control"] = dict(
        feature="t1 - t0, the label's own source (label_D = 1[t1-t0 >= D])",
        purpose=("must reach AUC ~ 1.0. If it does not, the pipeline cannot see "
                 "the answer even when handed it, and the arms' results are "
                 "uninterpretable."),
        test_auc_by_delta={str(D): auc(Y[te_m & OK[:, k], k],
                                       lk["scores"][te_m & OK[:, k], k])
                           for k, D in enumerate(DELTAS)},
        test_within_t0_auc_by_delta={str(D): wtauc(te_m, k, lk["scores"])
                                     for k, D in enumerate(DELTAS)})
    log("leakctl", lc["leak_control"]["test_auc_by_delta"])
    sh = run_mlp(D_OWN, X[:, OWN_IDX], "shufctl", max(args.mlp_epochs // 4, 3),
                 shuffle_train_labels=True)
    lc["shuffled_label_control"] = dict(
        purpose=("train labels permuted AND checkpoint selection blinded "
                 "(selection labels shuffled too); test AUC must sit at ~0.5 "
                 "under the SAME within-t0 metric the arms are judged on"),
        metric_note=("`test_auc_by_delta` is POOLED across entry steps, reported "
                     "for continuity only. It is NOT comparable to 0.5: a pooled "
                     "AUC partly measures the calendar (see within_t0_auc). The "
                     "chance test uses `test_within_t0_auc_by_delta.*.weighted`, "
                     "which is the metric the arms are judged on."),
        test_auc_by_delta={str(D): auc(Y[te_m & OK[:, k], k],
                                       sh["scores"][te_m & OK[:, k], k])
                           for k, D in enumerate(DELTAS)},
        test_within_t0_auc_by_delta={str(D): wtauc(te_m, k, sh["scores"])
                                     for k, D in enumerate(DELTAS)},
        selection_was_blinded_to_true_labels=True)
    log("shufctl", lc["shuffled_label_control"]["test_auc_by_delta"])
    log("shufctl within-t0",
        {D: (v or {}).get("weighted")
         for D, v in lc["shuffled_label_control"]
         ["test_within_t0_auc_by_delta"].items()})
    lc["feature_filter_verification"] = verify_sample_features(
        pop, cell_raw, seed=SEED_SPLIT + 1)
    log("feature verify", lc["feature_filter_verification"]["n_exact_match"],
        "/", lc["feature_filter_verification"]["n_compared"])
    lc["wallets_features_audit"] = dict(
        columns_used_as_features=0,
        columns_used_from_file=["Time step (to define t0/t1 and the label only)"],
        **wa)
    lc["lifetime_column_denial"] = dict(
        denied_names=LIFETIME_COLUMNS_DENIED,
        present_in_model_matrices=[c for c in FEAT_NAMES
                                   if c in LIFETIME_COLUMNS_DENIED],
        model_feature_names=FEAT_NAMES)
    ff = lc["feature_filter_verification"]
    lc["summary"] = {
        "all_features_filtered_on_step_le_t0": True,
        "feature_filter_verification_exact": bool(ff["n_mismatch"] == 0),
        "feature_filter_verification_not_inert": bool(
            ff["n_where_leq_differs_from_gt"] > 0),
        # Both metrics required to reach 1.0: a leak visible only in the pooled
        # column would be a calendar artefact rather than a leak.
        "leak_control_reaches_1": bool(
            all((v or 0) > 0.98
                for v in lc["leak_control"]["test_auc_by_delta"].values())
            and all((v or 0) > 0.98
                    for v in wt_vals(lc["leak_control"]
                                     ["test_within_t0_auc_by_delta"]))),
        # The chance test runs on the WITHIN-STEP control. The pooled column is
        # still emitted (the arms' numbers were quoted pooled before this
        # change) but 0.5 is not its null, so testing it against 0.5 asked the
        # wrong question of the wrong quantity.
        "shuffled_control_at_chance": bool(
            all(v is not None and abs(v - 0.5) < 0.05
                for v in wt_vals(lc["shuffled_label_control"]
                                 ["test_within_t0_auc_by_delta"]))),
        "no_lifetime_column_in_model_matrices": bool(
            not lc["lifetime_column_denial"]["present_in_model_matrices"]),
        "variance_instrument_positive_control_is_1": bool(
            wa["positive_control"]["frac_multi_step_addresses_varying"] == 1.0),
        "wf_num_timesteps_matches_nsteps": bool(
            wa["label_identity"]["n_mismatch"] == 0),
        "delta1_equals_recurrence": bool(
            r["delta1_equals_recurrence"]["identical"]),
        "naive_provided_column_baseline_shows_the_leak": bool(
            (r["naive_leaking_baseline"]["by_delta"]["1"]["auc_test"] or 0) > 0.98),
    }
    r["leakage_check"] = lc
    r["leakage_check_seconds"] = round(time.time() - t_lc, 1)
    log("leakage", lc["summary"])

    r["seconds_total"] = round(time.time() - t_start, 1)
    r["status"] = "ok"
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(to_native(r), fh, ensure_ascii=False, indent=2)
    write_txt(r)
    log("wrote", OUT_JSON)
    for name in ("mlp_feature_only", "graphsage", "tgn"):
        for D in DELTAS:
            b = r["arms"][name]["by_delta"][str(D)]
            print("%-18s D=%-2d  AUC %s [%s, %s]  acc %.4f vs degen %.4f  n=%d"
                  % (name, D, b["auc_test"], b["auc"]["lo"], b["auc"]["hi"],
                     b["accuracy_at_0p5"],
                     b["degenerate_accuracy_predict_negative"], b["n"]))
    for D in DELTAS:
        b = r["naive_leaking_baseline"]["by_delta"][str(D)]
        print("%-18s D=%-2d  AUC %s   [INADMISSIBLE: reads the answer]"
              % ("naive_provided", D, b["auc_test"]))
    return 0


def write_txt(r):
    L = []
    w = L.append
    w("E5p -- temporal GNN persistence prediction on Elliptic++")
    w("=" * 78)
    w("label : label_D = 1[ t1 - t0 >= D ], t0/t1 = first/last observed step.")
    w("        D = 1  <=>  'observed in >= 2 distinct steps' = E5-fin's")
    w("        recurrence label. D is a pre-registered free parameter: %s"
      % (r["meta"]["deltas"],))
    w("anchor: every feature is computed from step <= t0 only.")
    w("")
    p = r["population"]
    w("POPULATION  all addresses with >= 1 observed step: %d"
      % p["n_with_at_least_one_step"])
    w("            by class: %s" % (p["by_class"],))
    w("            (class 1=illicit 2=licit 3=unknown; the model is CLASS-BLIND)")
    w("")
    w("D=1 identity check: %d positives vs %d addresses with n_steps>=2 -- "
      "identical=%s" % (r["delta1_equals_recurrence"]["n_delta1_pos"],
                        r["delta1_equals_recurrence"]["n_nsteps_ge_2"],
                        r["delta1_equals_recurrence"]["identical"]))
    w("")
    w("CENSORING  (an address can satisfy t1-t0>=D only if t0 <= 49-D; those")
    w("that cannot are EXCLUDED from that Delta, never relabelled 0)")
    w("  %-4s %-10s %-10s %-11s %-11s %s"
      % ("D", "eligible", "excluded", "excl.share", "pos_rate", "pos_n"))
    for D in r["meta"]["deltas_censoring_table"]:
        c = r["censoring"][str(D)]
        w("  %-4s %-10d %-10d %-11.4f %-11.5f %d"
          % (D, c["eligible"], c["excluded_censored"], c["excluded_share"],
             c["pos_rate_eligible"], c["n_pos"]))
    w("")
    w("  eligible survival rate by class:")
    for D in r["meta"]["deltas"]:
        c = r["censoring"][str(D)]
        w("    D=%-3d illicit %.4f%% (n=%d)   licit %.4f%%   unknown %.4f%%   "
          "class12 %.4f%%"
          % (D, 100 * c["illicit"]["pos_rate"], c["illicit"]["eligible"],
             100 * c["licit"]["pos_rate"], 100 * c["unknown"]["pos_rate"],
             100 * c["cohort_class12"]["pos_rate"]))
    w("")
    sz = r["t0_structural_zero"]
    w("STRUCTURAL ZERO: %d addresses enter at t0=49, %d more at t0=45..48."
      % (sz["t0_49_n"], sz["t0_45_to_48_n"]))
    w("  %s" % sz["note"])
    w("")
    s = r["split"]
    w("SPLIT by address, seed %d: train=%d val=%d test=%d (test class1/2=%d)"
      % (s["seed"], s["train"], s["val"], s["test"], s["test_only_class12"]))
    w("      overlap train/val/test = %d / %d / %d"
      % (s["overlap_train_val"], s["overlap_train_test"], s["overlap_val_test"]))
    g = r["graph"]
    w("GRAPH  %d edges with multiplicity -> %d distinct (src,dst,step) -> %d"
      % (g["n_edges_with_multiplicity"], g["n_distinct_src_dst_step"],
         g["undirected_distinct_edges"]))
    w("       %d nodes; dedup shrink %.4f"
      % (g["n_nodes_in_graph"], g["dedup_shrink"]))
    w("")
    w("ARMS  (test set, eligible for that Delta; multi-task, one head per Delta)")
    w("-" * 78)
    for name in ("mlp_feature_only", "graphsage", "tgn"):
        a = r["arms"][name]
        w("")
        w("%s   [%s epochs, %d params, %.0fs]"
          % (name, a["epochs"], a["n_params"], a["seconds"]))
        w("  features: %s" % a["features"])
        w("  best mean val AUC %.4f" % a["val_auc_mean"])
        if "memory_absmean_end" in a:
            w("  TGN memory |.| mean at end: %.5f (changed=%s)"
              % (a["memory_absmean_end"], a["memory_changed"]))
        w("  %-4s %-9s %-8s %-26s %-10s %-10s %s"
          % ("D", "n", "pos", "AUC [95% CI]", "acc", "degen", "within-t0"))
        for D in r["meta"]["deltas"]:
            b = a["by_delta"][str(D)]
            wt = b["within_t0_auc"]["weighted"]
            w("  %-4d %-9d %-8d %.4f [%.4f, %.4f]   %-10.4f %-10.4f %s"
              % (D, b["n"], b["n_pos"], b["auc_test"], b["auc"]["lo"],
                 b["auc"]["hi"], b["accuracy_at_0p5"],
                 b["degenerate_accuracy_predict_negative"],
                 "n/a" if wt is None else "%.4f" % wt))
            for k, v in b["by_class"].items():
                if v["auc"] is None or v["auc"].get("auc") is None:
                    w("        %-8s n=%-7d pos_rate=%.4f  AUC n/a"
                      % (k, v["n"], v["pos_rate"]))
                else:
                    w("        %-8s n=%-7d pos_rate=%.4f  AUC %.4f"
                      % (k, v["n"], v["pos_rate"], v["auc"]["auc"]))
            cs = b["class12_subset"]
            w("        class1/2 subset n=%d  AUC %s  (E5-fin-comparable)"
              % (cs["n"], cs["auc_test"]))
    w("")
    nv = r["naive_leaking_baseline"]
    w("THE PLAN'S MLP BASELINE AS THE PLAN SPECIFIES IT -- AND WHY IT IS NOT USED")
    w("-" * 78)
    w("  an MLP on all %d provided columns (address-level lifetime aggregates),"
      % len(nv["feature_columns"]))
    w("  same split, same labels, same architecture as `mlp_feature_only`:")
    w("  %-4s %-9s %-26s %s" % ("D", "n", "AUC [95% CI]", "pos_rate"))
    for D in r["meta"]["deltas"]:
        b = nv["by_delta"][str(D)]
        w("  %-4s %-9d %.4f [%.4f, %.4f]   %.5f"
          % (D, b["n"], b["auc_test"], b["auc"]["lo"], b["auc"]["hi"],
             b["pos_rate"]))
    w("  %s" % nv["admissibility"])
    w("  %s" % nv["note"])
    w("")
    w("LEAKAGE CHECK  (%.0fs)" % r["leakage_check_seconds"])
    w("-" * 78)
    lc = r["leakage_check"]
    w("  (a) leak control -- MLP on t1-t0, the label's own source:")
    for D, v in lc["leak_control"]["test_auc_by_delta"].items():
        w("        D=%-3s test AUC %s   (must be ~1.0)" % (D, v))
    w("  (b) shuffled-label control -- train labels permuted:")
    for D, v in lc["shuffled_label_control"]["test_auc_by_delta"].items():
        w("        D=%-3s test AUC %s   (must be ~0.5)" % (D, v))
    ff = lc["feature_filter_verification"]
    w("  (c) feature-filter verification, recomputed from the raw CSVs:")
    w("        sampled %d, exact match %d, mismatch %d"
      % (ff["n_sampled"], ff["n_exact_match"], ff["n_mismatch"]))
    w("        step<=t0 differs from step>t0 in %d/%d (%.2f%%) -- a filter that"
      % (ff["n_where_leq_differs_from_gt"], ff["n_compared"],
         100 * ff["frac_where_leq_differs_from_gt"]))
    w("        never differed would be inert, and the equality above vacuous")
    wa = lc["wallets_features_audit"]
    w("  (d) wallets_features audit: %d/%d columns constant within address; %d"
      % (wa["columns_constant_within_address"], wa["n_columns_examined"],
         wa["columns_used_as_features"]))
    w("        columns used as features (only 'Time step' is read at all)")
    pc = wa["positive_control"]
    w("      positive control on that instrument: 'Time step' varies for %.4f of"
      % (pc["frac_multi_step_addresses_varying"],))
    w("      %s (overall %.4f of all addresses)"
      % (pc["measured_on"], pc["overall_frac_varying"]))
    li = wa["label_identity"]
    w("  (e) wf['num_timesteps_appeared_in'] == n_steps_observed: %d mismatches"
      % (li["n_mismatch"],))
    w("      over %d addresses -- at D=1 that column IS the label"
      % (li["compared"],))
    w("      denied lifetime columns present in model matrices: %s"
      % (lc["lifetime_column_denial"]["present_in_model_matrices"],))
    w("")
    w("  summary: %s" % json.dumps(lc["summary"], ensure_ascii=False))
    w("")
    w("CLASS-BLINDNESS: class is never an input. Eligible survival differs")
    w("strongly by class (see the censoring table), so part of any well-fitting")
    w("model's AUC is that class-correlated gap, recovered from behaviour.")
    w("")
    w("runtime %.1fs   seeds %s" % (r["seconds_total"], r["meta"]["seeds"]))
    with open(OUT_TXT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
