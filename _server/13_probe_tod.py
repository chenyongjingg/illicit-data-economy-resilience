#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""13_probe_tod.py -- how coarse is each market's clock?

12_ showed every Cryptonia timestamp it printed ending in 22:00:00 or 23:00:00,
while Apollon's carried ordinary clock times (09:38:00, 01:27:00). If a market's
time axis is date-only, then any analysis at sub-day resolution silently compares
a real clock against a rounded one -- and a "sellers moved markets in November"
finding could be an artefact of two markets having different timestamp precision.

So before E1 uses time at all, measure the resolution of each market's clock:
how many distinct second-of-day values exist, and what they are.
"""
from __future__ import annotations

import os

import pandas as pd

pd.set_option("display.width", 200)
WORK = "/root/cis/work"
MARKETS = ["Empire", "Cannazon", "Apollon", "Cryptonia", "CannaHome"]

ks = pd.read_parquet(os.path.join(WORK, "kilos_reviews.parquet"))
ts = pd.to_datetime(pd.to_numeric(ks["f2"], errors="coerce"), unit="s", errors="coerce")
d = ks.assign(ts=ts, market=ks["market"].astype(str).str.strip())
d = d[d["market"].isin(MARKETS) & d["ts"].notna()].copy()

print("=" * 78)
print("1. Seconds-of-day actually present, per market")
print("=" * 78)
for m in MARKETS:
    g = d.loc[d["market"] == m, "ts"]
    if not len(g):
        continue
    sod = (g.dt.hour * 3600 + g.dt.minute * 60 + g.dt.second)
    nun = sod.nunique()
    top = sod.value_counts().head(4)
    top_s = " | ".join("%02d:%02d:%02d x%d" % (v // 3600, (v % 3600) // 60, v % 60, c)
                       for v, c in top.items())
    print("  %-11s n=%-7d distinct seconds-of-day=%-6d  %s"
          % (m, len(g), nun, top_s))
    print("  %-11s   seconds always 00: %s ; minutes always 00: %s"
          % ("", bool((g.dt.second == 0).all()), bool((g.dt.minute == 0).all())))

print("")
print("=" * 78)
print("2. What fraction of rows sit at the single commonest second-of-day?")
print("=" * 78)
for m in MARKETS:
    g = d.loc[d["market"] == m, "ts"]
    if not len(g):
        continue
    sod = (g.dt.hour * 3600 + g.dt.minute * 60 + g.dt.second)
    vc = sod.value_counts()
    print("  %-11s top=%.1f%%  top3=%.1f%%  n_distinct=%d"
          % (m, 100.0 * vc.iloc[0] / len(g),
             100.0 * vc.head(3).sum() / len(g), len(vc)))

print("")
print("=" * 78)
print("3. Date-only collapse: does the market look the same at daily resolution?")
print("=" * 78)
d["day"] = d["ts"].dt.floor("D")
for m in MARKETS:
    g = d[d["market"] == m]
    if not len(g):
        continue
    per_day = g.groupby("day").size()
    print("  %-11s days=%-6d reviews/day median=%-6.0f max=%-6d  days with >1 "
          "review in the same SECOND: %d"
          % (m, len(per_day), per_day.median(), per_day.max(),
             int(g.groupby("ts").size().gt(1).sum())))

print("")
print("=" * 78)
print("4. Cryptonia's terminal date, at daily resolution (is the end sharp?)")
print("=" * 78)
for m in ["Cryptonia", "Cannazon", "Empire"]:
    g = d[d["market"] == m]
    if not len(g):
        continue
    per_day = g.groupby("day").size().sort_index()
    print("  %s last 8 active days:" % m)
    print("    %s" % dict(per_day.tail(8)))
    print("    max day: %s (%d reviews)" % (per_day.idxmax().date(), per_day.max()))

print("\nPROBE_TOD_DONE")
