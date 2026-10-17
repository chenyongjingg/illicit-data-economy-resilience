#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""07_probe_social.py -- read the social-layer table schemas before designing E1/E4.

AlphaBay is the only dated illicit-market dataset reachable here, and C-26 already
established it carries no vendor identifier, so E4's unit has to be the item. This
prints what the tables actually contain -- columns, dtypes, real value distributions
-- so the experiment design is written against the data rather than against the
sprint plan's assumptions about it.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 60)
WORK = "/root/cis/work"

print("=" * 78)
print("work/ contents")
print("=" * 78)
for f in sorted(os.listdir(WORK)):
    p = os.path.join(WORK, f)
    print("  %-34s %10.1f MB" % (f, os.path.getsize(p) / 1e6))

for name in ("ab_listings", "ab_feedback", "hansa", "kilos", "valhalla",
             "ioc_threatfox", "ioc_urlhaus"):
    p = os.path.join(WORK, name + ".parquet")
    if not os.path.exists(p):
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
        nn = s.notna().sum()
        sample = ""
        try:
            vc = s.dropna().astype(str).value_counts().head(2)
            sample = " | ".join("%s(%d)" % (k[:34], v) for k, v in vc.items())
        except Exception:  # noqa: BLE001
            pass
        print("    %-26s %-10s nonnull=%-8d %s" % (c, str(s.dtype), nn, sample[:90]))
    print("  head(2):")
    print(d.head(2).to_string()[:1200])

print("\nPROBE_SOCIAL_DONE")
