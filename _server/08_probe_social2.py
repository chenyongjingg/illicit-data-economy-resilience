#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""08_probe_social2.py -- the social tables, under their real filenames.

The previous probe guessed `ab_listings`/`hansa`/`kilos`/`valhalla`; the files are
actually `ab_items`/`hansa_reviews`/`kilos_reviews`/`valhalla_listings`. Guessing a
filename and finding nothing is indistinguishable from the table not existing --
which is why the first probe also printed a directory listing, and that is the only
reason the gap was visible at all.
"""
from __future__ import annotations

import os

import pandas as pd

pd.set_option("display.width", 210)
pd.set_option("display.max_columns", 60)
WORK = "/root/cis/work"

for name in ("ab_items", "hansa_reviews", "kilos_reviews", "valhalla_listings"):
    p = os.path.join(WORK, name + ".parquet")
    if not os.path.exists(p):
        print("\n!! MISSING: %s" % p)
        continue
    print("")
    print("=" * 78)
    print("%s.parquet" % name)
    print("=" * 78)
    d = pd.read_parquet(p)
    print("  shape: %s" % (d.shape,))
    print("  columns:")
    for c in d.columns:
        s = d[c]
        vc = s.dropna().astype(str).value_counts().head(2)
        sm = " | ".join("%s(%d)" % (str(k)[:36], v) for k, v in vc.items())
        print("    %-24s %-14s nonnull=%-8d %s" % (c, str(s.dtype), s.notna().sum(), sm[:88]))
    print("  head(3):")
    print(d.head(3).to_string()[:1400])

# ---------------------------------------------------------------- the spine
print("")
print("=" * 78)
print("The dated spine: can items be linked to feedback over time?")
print("=" * 78)
items = pd.read_parquet(os.path.join(WORK, "ab_items.parquet"))
fb = pd.read_parquet(os.path.join(WORK, "ab_feedback.parquet"))
print("  items rows: %d ; feedback rows: %d" % (len(items), len(fb)))
num_cols = [c for c in items.columns if "num" in c.lower() or "id" in c.lower()]
print("  candidate item-key columns in ab_items: %s" % num_cols)
if num_cols:
    k = num_cols[0]
    print("  %s: n=%d distinct=%d min=%s max=%s"
          % (k, items[k].notna().sum(), items[k].nunique(),
             items[k].min(), items[k].max()))
    fbi = set(fb["item_number"].dropna().astype("int64"))
    ii = set(items[k].dropna().astype("int64"))
    print("  feedback item_number: distinct=%d  range %s..%s"
          % (len(fbi), min(fbi), max(fbi)))
    print("  intersection(items, feedback): %d (%.1f%% of items)"
          % (len(ii & fbi), 100.0 * len(ii & fbi) / max(len(ii), 1)))
print("")
print("  feedback span: %s .. %s" % (fb["ts"].min(), fb["ts"].max()))
print("  feedback per month (first 8 / last 8):")
m = fb.set_index("ts").resample("MS").size()
print("    %s" % dict(m.head(8)))
print("    %s" % dict(m.tail(8)))
print("  rating: %s" % dict(fb["rating"].value_counts()))

print("\nPROBE_SOCIAL2_DONE")
