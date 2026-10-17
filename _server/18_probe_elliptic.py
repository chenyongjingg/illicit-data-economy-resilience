#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""18_probe_elliptic.py -- what can Elliptic++ actually support?

The sprint plan assigns the financial layer to Bitcoin (Elliptic++). Before any
experiment is designed, this establishes what the files contain and, just as
importantly, what the labels mean -- because the whole dataset is built for
*detection*, and repurposing it for a persistence question requires knowing
whether the columns even carry time.

The README's own counts are used as a checksum rather than taken on faith:
822,942 labelled addresses, 1,268,260 nodes, 2,868,964 addr-addr edges,
1,314,241 addr-tx-addr edges, 49 time steps, classes 14,266 / 251,088 / 557,588.

Deliberately reads headers and bounded samples only: txs_features.csv is 694.8 MB
and wallets_features.csv 606.5 MB, and a probe that loads them whole costs minutes
to answer questions a header and 3 rows answer immediately.
"""
from __future__ import annotations

import os

import pandas as pd

BASE = "/root/cis/data/EllipticPlusPlus-main"
ACT = os.path.join(BASE, "Actors Dataset")
TXN = os.path.join(BASE, "Transactions Dataset")

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)


def head_cols(path, n=3, label=None):
    print("")
    print("=" * 78)
    print("%s  (%s)" % (label or os.path.basename(path),
                        "%.1f MB" % (os.path.getsize(path) / 1e6)))
    print("=" * 78)
    d = pd.read_csv(path, nrows=n)
    print("  ncols=%d" % d.shape[1])
    print("  first 14 columns: %s" % list(d.columns[:14]))
    if d.shape[1] > 14:
        print("  last 8 columns:   %s" % list(d.columns[-8:]))
    tc = [c for c in d.columns if "time" in str(c).lower() or str(c).lower().startswith("t")]
    print("  time-suggesting columns: %s" % (tc[:20] if tc else "none"))
    print("  sample row:")
    print("   ", d.iloc[0].head(14).to_dict())
    return d


print("=" * 78)
print("Transactions Dataset")
print("=" * 78)
head_cols(os.path.join(TXN, "txs_classes.csv"), 5, "txs_classes.csv")
head_cols(os.path.join(TXN, "txs_edgelist.csv"), 3, "txs_edgelist.csv")
txf = head_cols(os.path.join(TXN, "txs_features.csv"), 3, "txs_features.csv")

print("")
print("=" * 78)
print("Actors Dataset")
print("=" * 78)
head_cols(os.path.join(ACT, "wallets_classes.csv"), 5, "wallets_classes.csv")
wf = head_cols(os.path.join(ACT, "wallets_features.csv"), 3, "wallets_features.csv")

# ------------------------------------------------- the time-step structure
print("")
print("=" * 78)
print("Does wallets_features carry per-time-step counts?")
print("=" * 78)
cols = list(wf.columns)
ts_cols = [c for c in cols if c.endswith("_Time Step")]
print("  columns ending in '_Time Step': %d" % len(ts_cols))
if ts_cols:
    print("  e.g. %s" % ts_cols[:12])
    print("  -> %d distinct time steps implied" % len(set(
        c.rsplit("_", 2)[0] for c in ts_cols)))
base_names = sorted(set(c.rsplit("_", 2)[0] for c in ts_cols)) if ts_cols else []
print("  distinct measured quantities: %d" % len(base_names))
print("  %s" % base_names[:20])
other = [c for c in cols if c not in ts_cols]
print("")
print("  non-time-step columns (%d): %s" % (len(other), other[:26]))

print("")
print("=" * 78)
print("Class distribution and time-step coverage")
print("=" * 78)
wc = pd.read_csv(os.path.join(ACT, "wallets_classes.csv"))
print("  wallets_classes: %d rows; class counts %s"
      % (len(wc), dict(wc["class"].value_counts().sort_index())))
print("  README claims 14,266 / 251,088 / 557,588 = 822,942 -> %s"
      % ("MATCH" if len(wc) == 822942 else "MISMATCH"))
tc = pd.read_csv(os.path.join(TXN, "txs_classes.csv"))
print("  txs_classes: %d rows; class counts %s"
      % (len(tc), dict(tc["class"].value_counts().sort_index())))

print("")
print("  the label semantics, which decide what any analysis can claim:")
print("    class 1 = illicit, class 2 = licit, class 3 = unknown")
print("    per the repo README these are ACTOR-level determinations -- an address")
print("    is labelled by whether it was ever involved in illicit activity, not by")
print("    what it was doing at a given time step.")

print("\nPROBE_ELLIPTIC_DONE")
