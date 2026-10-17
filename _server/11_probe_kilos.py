#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""11_probe_kilos.py -- can vendor identity be established across markets?

E1 wants to measure the social layer's central resilience mechanism: when one
market fails, do its sellers continue elsewhere? Answering that needs a seller
identity that survives a market boundary.

A vendor *name* is not that. The same handle in two markets may be two different
people, and one person may use two handles in one market. Name matching therefore
errs in both directions at once -- it is neither an upper nor a lower bound, and
no amount of care makes it one. So before E1 is designed, this probe asks whether
anything stronger is present: a PGP key, an account id, a profile URL.

It also pins down the time axis, because `09_` showed one market (Samsara,
n=10,216) carries f2 == 0 for every row -- an epoch date, i.e. a null marker, not
a timestamp. Any time series built without excluding it would silently contain
~10k events in 1970.
"""
from __future__ import annotations

import os
import re

import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 60)
WORK = "/root/cis/work"

ks = pd.read_parquet(os.path.join(WORK, "kilos_reviews.parquet"))
print("=" * 78)
print("kilos_reviews.parquet  shape=%s" % (ks.shape,))
print("=" * 78)
for c in ks.columns:
    s = ks[c]
    nn = int(s.notna().sum())
    try:
        vc = s.dropna().astype(str).value_counts().head(3)
        sm = " | ".join("%s(%d)" % (k[:40], v) for k, v in vc.items())
    except Exception:  # noqa: BLE001
        sm = ""
    print("  %-22s %-12s nonnull=%-8d %s" % (c, str(s.dtype), nn, sm[:100]))

print("")
print("=" * 78)
print("Is there any identity key stronger than the handle?")
print("=" * 78)
BLOB = re.compile(r"pgp|fingerprint|public key|-----BEGIN|btc|bitcoin|wallet|"
                  r"jabber|xmpp|wickr|session|telegram|matrix|tor|onion|", re.I)
for c in ks.columns:
    s = ks[c].dropna().astype(str)
    if not len(s):
        continue
    hit = s.str.contains(BLOB, regex=True, na=False)
    if hit.any():
        print("  %-22s %6d/%d rows match identity-ish vocabulary; e.g. %r"
              % (c, int(hit.sum()), len(s), s[hit].iloc[0][:90]))

print("")
print("=" * 78)
print("Time axis, per market, with the null marker handled")
print("=" * 78)
f2 = pd.to_numeric(ks["f2"], errors="coerce")
ts = pd.to_datetime(f2, unit="s", errors="coerce")
print("  f2 == 0 rows: %d  (these become 1970-01-01, which is NOT a date)"
      % int((f2 == 0).sum()))
print("  f2 == 0 by market: %s" % dict(ks.loc[f2 == 0, "market"].value_counts()))
ok = (ts > "2015-01-01") & (ts < "2030-01-01")
print("  usable rows after dropping non-dates: %d/%d" % (int(ok.sum()), len(ks)))

mk = pd.DataFrame({"m": ks["market"].astype(str), "ts": ts[ok]}).dropna()
print("")
print("  %-16s %9s %9s %s .. %s" % ("market", "reviews", "sellers", "first", "last"))
for m, g in mk.groupby("m"):
    if len(g) < 100:
        print("  %-16s %9d   (too small / not a market label)" % (str(m)[:16], len(g)))
        continue
    print("  %-16s %9d %9d %s .. %s"
          % (m[:16], len(g), ks.loc[g.index, "vendor"].nunique(),
             g["ts"].min().date(), g["ts"].max().date()))

print("")
print("=" * 78)
print("Overlap: are the same handles present in more than one market?")
print("=" * 78)
good = [m for m in ks["market"].astype(str).unique()
        if len(str(m)) <= 24 and "\n" not in str(m)]
sub = ks[ks["market"].astype(str).isin(good)][["market", "vendor"]].dropna()
sub["market"] = sub["market"].astype(str).str.strip()
sub["vendor"] = sub["vendor"].astype(str).str.strip()
sub = sub[(sub["vendor"] != "") & (sub["vendor"].str.lower() != "nan")]
per = sub.groupby("vendor")["market"].nunique()
n_multi = int((per > 1).sum())
print("  distinct seller handles: %d" % len(per))
print("  present in >1 market:    %d (%.1f%%)" % (n_multi, 100.0 * n_multi / len(per)))
print("  reviews written by those handles: %d/%d (%.1f%%)"
      % (int(sub["vendor"].isin(per[per > 1].index).sum()), len(sub),
         100.0 * sub["vendor"].isin(per[per > 1].index).mean()))
print("")
print("  CAVEAT THAT DECIDES HOW THIS MAY BE USED: a matching handle is not the")
print("  same person. Nothing in this table ties a handle to a key, so overlap is")
print("  a *candidate* mobility signal whose error runs both ways. E1 may report")
print("  it only as a descriptive structural statistic, never as vendor migration.")
print("")
top = per[per > 1].head(10)
for v in top.index:
    ms = sorted(sub.loc[sub["vendor"] == v, "market"].unique())
    print("    %-28s %s" % (v[:28], ms))

print("\nPROBE_KILOS_DONE")
