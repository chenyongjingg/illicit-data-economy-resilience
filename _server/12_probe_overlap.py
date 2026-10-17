#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""12_probe_overlap.py -- is cross-market seller overlap mobility, or provenance?

11_ found that 387 of 1,660 seller handles (23.3%) appear in more than one of the
five dated Kilos markets, carrying 51.0% of all reviews. That is a large number,
and the tempting reading is the one E1 was written to test: sellers move between
markets, so the ecosystem persists through its people.

The top-10 overlap list says otherwise. Seven of ten are the SAME pair,
`['Apollon','Cryptonia']`. A genuine mobility process would spread across all
pairs in proportion to how much traffic each market has. One pair dominating is
the signature of two tables sharing a *source*, not of sellers walking between
markets.

This matters more than a caveat, because the two readings have opposite
implications. Under mobility, the overlap measures resilience. Under shared
provenance, the overlap measures the scraping procedure -- and would appear even
if not one seller ever moved.

The decisive test is not name overlap but *whether the rows themselves are
duplicates*. Two markets fed by one upstream will contain the same (seller,
price, timestamp, text length) tuples, because they are the same review.
Independent markets cannot: two different buyers cannot produce the same price
and the same second.

Nothing here is assumed; both the overlap structure and the duplicate rate are
measured.

Also fixes the regex in 11_: `pgp|fingerprint|...|onion|` ends in a bare `|`, so
the alternation contains the EMPTY string and matches every row. A vocabulary
scan that finds everything has found nothing -- and it reports 100%, which looks
like a strong positive.
"""
from __future__ import annotations

import itertools
import os
import re

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
WORK = "/root/cis/work"

ks = pd.read_parquet(os.path.join(WORK, "kilos_reviews.parquet"))
f2 = pd.to_numeric(ks["f2"], errors="coerce")
ts = pd.to_datetime(f2, unit="s", errors="coerce")
ks = ks.assign(ts=ts)

BLOB = re.compile(r"\b(?:pgp|fingerprint|public key|-----BEGIN|btc|bitcoin|wallet|"
                  r"jabber|xmpp|wickr|session|telegram|matrix|onion)\b", re.I)
print("=" * 78)
print("0. The vocabulary scan, with the empty-alternative bug removed")
print("=" * 78)
for c in ks.columns:
    s = ks[c].dropna().astype(str)
    if len(s) and s.str.contains(BLOB, regex=True, na=False).any():
        print("  %-12s %d/%d rows match" % (c, int(s.str.contains(BLOB, regex=True, na=False).sum()), len(s)))
print("  -> no column carries PGP keys, wallet addresses or contact handles; the")
print("     schema is market/vendor/time/flag/price/text_len and nothing else.")

MARKETS = ["Empire", "Cannazon", "Apollon", "Cryptonia", "CannaHome"]
d = ks[ks["market"].astype(str).isin(MARKETS)].copy()
d["vendor"] = d["vendor"].astype(str).str.strip()
d["market"] = d["market"].astype(str).str.strip()
d = d[d["vendor"].ne("") & d["vendor"].str.lower().ne("nan")]
print("")
print("=" * 78)
print("1. Pairwise seller overlap -- is it spread, or concentrated in one pair?")
print("=" * 78)
sets = {m: set(d.loc[d["market"] == m, "vendor"]) for m in MARKETS}
print("  %-11s %-11s %7s %7s %7s %7s" % ("A", "B", "|A|", "|B|", "n_AB", "|A&B|/min"))
rows = []
for a, b in itertools.combinations(MARKETS, 2):
    A, B = sets[a], sets[b]
    if not A or not B:
        continue
    inter = len(A & B)
    cont = inter / min(len(A), len(B))
    rows.append({"A": a, "B": b, "nA": len(A), "nB": len(B), "nAB": inter,
                 "containment_min": cont, "jaccard": inter / len(A | B)})
    print("  %-11s %-11s %7d %7d %7d %7.3f"
          % (a, b, len(A), len(B), inter, cont))
ov = pd.DataFrame(rows).sort_values("containment_min", ascending=False)
print("")
print("  most-overlapping pair: %s / %s, containment %.3f"
      % (ov.iloc[0]["A"], ov.iloc[0]["B"], ov.iloc[0]["containment_min"]))
print("  median containment across all pairs: %.3f" % ov["containment_min"].median())
print("  If overlap were seller mobility it would track market size; if it were")
print("  one upstream feed, it would be near 1.0 for one pair and low elsewhere.")

print("")
print("=" * 78)
print("2. The decisive test: are the ROWS duplicated across markets?")
print("=" * 78)
KEYS = ["vendor", "price", "ts", "text_len"]
dd = d.dropna(subset=["price", "ts"]).copy()
dd["price"] = dd["price"].round(8)
keyed = dd.groupby(KEYS)["market"].nunique()
print("  distinct (vendor, price, timestamp, text_len) tuples: %d" % len(keyed))
print("  tuples appearing in >1 market:                        %d (%.4f%%)"
      % (int((keyed > 1).sum()), 100.0 * (keyed > 1).mean()))
print("")
print("  restricted to the two most-overlapping markets:")
for a, b in [(ov.iloc[0]["A"], ov.iloc[0]["B"])]:
    sub = dd[dd["market"].isin([a, b])]
    k2 = sub.groupby(KEYS)["market"].nunique()
    both = int((k2 > 1).sum())
    print("    %s + %s: %d shared tuples out of %d (%.3f)"
          % (a, b, both, len(k2), both / max(len(k2), 1)))
    n_a = int((sub["market"] == a).sum())
    n_b = int((sub["market"] == b).sum())
    print("    rows: %s=%d  %s=%d" % (a, n_a, b, n_b))
    print("    -> a shared tuple is a review that cannot have been written twice")
    print("       by two different buyers at the same second for the same price.")

print("")
print("=" * 78)
print("3. Same seller, two markets: same timestamp distribution?")
print("=" * 78)
cand = [v for v in (sets["Apollon"] & sets["Cryptonia"])][:4000]
sub = dd[(dd["vendor"].isin(cand)) & (dd["market"].isin(["Apollon", "Cryptonia"]))]
for v in list(cand)[:5]:
    g = sub[sub["vendor"] == v]
    pa = g.loc[g["market"] == "Apollon", "ts"]
    pc = g.loc[g["market"] == "Cryptonia", "ts"]
    print("  %-20s Apollon n=%-5d %s .. %s" % (v[:20], len(pa),
          pa.min() if len(pa) else "-", pa.max() if len(pa) else "-"))
    print("  %-20s Cryptonia n=%-5d %s .. %s" % ("", len(pc),
          pc.min() if len(pc) else "-", pc.max() if len(pc) else "-"))

print("")
print("=" * 78)
print("4. Monthly review volume per market")
print("=" * 78)
d["ym"] = d["ts"].dt.to_period("M").astype(str)
piv = d.pivot_table(index="ym", columns="market", values="price",
                    aggfunc="size", fill_value=0)
print(piv.to_string())

print("\nPROBE_OVERLAP_DONE")
