# -*- coding: utf-8 -*-
"""Measure, on the real data, whether the verifier can ever see a self-loop.

CLAIM UNDER TEST
----------------
`verify_sample_features` filters `e = e[src != dst]` and then counts
`(is_src & is_dst).sum()` as `c_self_loops`. Those two lines cannot both be
right: after the filter, `src == dst` never holds, so the count is structurally
0 -- and the 6 non-exact rows in the landed artefact are that defect, not a leak.

This mirrors the writer's own construction EXACTLY, then counts self-loops in
BOTH frames for the addresses the artefact recorded as mismatches. If the stored
value equals the count in the RAW join, the stored value is right and the
verifier is the thing that is wrong.

Also sizes the gap: how many addresses in the whole join have a self-loop at all,
which is the population that this column's verification silently cannot cover.
"""
import io
import os

import numpy as np
import pandas as pd

BASE = "/root/cis/data/EllipticPlusPlus-main"
ACT = os.path.join(BASE, "Actors Dataset")
TXD = os.path.join(BASE, "Transactions Dataset")

at = pd.read_csv(os.path.join(ACT, "AddrTx_edgelist.csv"))
ta = pd.read_csv(os.path.join(ACT, "TxAddr_edgelist.csv"))
txf = pd.read_csv(os.path.join(TXD, "txs_features.csv"),
                  usecols=["txId", "Time step"])
at.columns = ["src", "txId"]
ta.columns = ["txId", "dst"]
e = at.merge(ta, on="txId", how="inner").merge(txf, on="txId", how="inner")
print("joined rows: %d" % len(e))

n_self_rows = int((e["src"].values == e["dst"].values).sum())
print("rows with src == dst (self-loops) in the join: %d" % n_self_rows)
self_addr = np.unique(e["src"].values[e["src"].values == e["dst"].values])
print("distinct addresses carrying >=1 self-loop: %d" % len(self_addr))

# exactly the writer's next line
ef = e[e["src"].values != e["dst"].values].reset_index(drop=True)
print("after the writer's `src != dst` filter: %d rows" % len(ef))
print()

# (address, t0, stored c_self_loops) read from the landed artefact
TARGETS = [
    ("12ocyHJ5ENZHkJ3hshQxZpdkpBgX7kNLeN", 17, 1.0),
    ("1621vrzn9enwiDHMU99nBEXh1HLoWv7Zhn", 19, 1.0),
    ("1DaWUaX5d3Tc9DX7tru5EvjNw1sW4MmfuT", 12, 1.0),
    ("1GgRNMZ7FsCT7YipuzfH4a2Yc9BeThFi1h", 5, 2.0),
    ("1MwADHm7o9vJgB5WT22dXEQzhwB4GYxXPA", 24, 1.0),
]

print("%-36s %4s %7s %9s %10s  %s"
      % ("address", "t0", "stored", "raw<=t0", "filt<=t0", "verdict"))
ok = bad = 0
for a, t0, stored in TARGETS:
    raw = e[(e["src"].values == a) & (e["dst"].values == a)
            & (e["Time step"].values <= t0)]
    flt = ef[(ef["src"].values == a) & (ef["dst"].values == a)
             & (ef["Time step"].values <= t0)]
    verdict = "stored == RAW" if float(len(raw)) == stored else "stored != RAW"
    ok += (float(len(raw)) == stored)
    bad += (float(len(raw)) != stored)
    print("%-36s %4d %7.0f %9d %10d  %s"
          % (a, t0, stored, len(raw), len(flt), verdict))

print()
print("%d/%d of the recorded mismatches have a stored c_self_loops that the RAW"
      " join reproduces and the VERIFIER's frame cannot (always 0)."
      % (ok, len(TARGETS)))
if bad:
    print("WARNING: %d did NOT reproduce -- do not claim the verifier is the"
          " sole cause." % bad)
