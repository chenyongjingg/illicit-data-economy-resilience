#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""17_E1_products.py -- why did Cryptonia's sellers move and Cannazon's not?

`16_` produced the sharpest number in E1 so far. Of sellers naive to Apollon
before 2019-11-18, those from Cryptonia entered Apollon at 21.0% against a control
rate of 7.4% (OR 3.34, p=3.5e-06). Those from Cannazon entered at 7.1% against the
same 7.4% control (OR 0.97, p=1). Two markets die on the same day; one population
substitutes and the other does not.

The natural explanation is product-market overlap: Cryptonia was a general market
and Apollon was too, so its sellers could redeploy; Cannazon was a cannabis
specialist, so its sellers had nowhere comparable to go. That explanation is
attractive and it is **not established by anything measured so far** -- the Kilos
table has no category column. This script asks what the available columns can and
cannot say about it, rather than assuming the story.

Available: `price`, `text_len`, and `f3` (values 1 / -1 / 0, plausibly a feedback
polarity). Not available: product category, so the overlap hypothesis cannot be
tested directly and will be reported as untested.

Three things ARE testable and each could refute the story:
  1. If Cannazon's prices already sat in Apollon's range, then price overlap is
     not what separates the two populations and the story loses its mechanism.
  2. If Cannazon-only sellers were simply less active overall, their non-entry is
     a size effect, not a specialist effect.
  3. If Cannazon-only sellers ALSO disappeared from every other market after the
     shock while Cryptonia-only sellers stayed, that is direct evidence of
     specialists having nowhere to go -- and it is the finding, not a caveat.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

WORK = "/root/cis/work"
RESULTS = "/root/cis/results"

MARKETS = ["Empire", "Cannazon", "Apollon", "Cryptonia", "CannaHome"]
DEAD = ["Cryptonia", "Cannazon"]
EVENT = pd.Timestamp("2019-11-18")
PRE0 = pd.Timestamp("2019-06-03")
POST1 = pd.Timestamp("2020-01-12")

_L: list[str] = []
R: dict = {}


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _L.append(s)


def sep(t):
    log("")
    log("=" * 78)
    log(t)
    log("=" * 78)


def main():
    log("=" * 78)
    log("E1 follow-up -- WHAT SEPARATES THE SELLERS WHO MOVED FROM THOSE WHO DID NOT")
    log("=" * 78)

    ks = pd.read_parquet(os.path.join(WORK, "kilos_reviews.parquet"))
    ts = pd.to_datetime(pd.to_numeric(ks["f2"], errors="coerce"), unit="s",
                        errors="coerce")
    d = ks.assign(ts=ts, market=ks["market"].astype(str).str.strip(),
                  vendor=ks["vendor"].astype(str).str.strip(),
                  f3n=pd.to_numeric(ks["f3"], errors="coerce"))
    d = d[d["market"].isin(MARKETS) & d["ts"].notna()]
    d = d[(d["vendor"] != "") & (d["vendor"].str.lower() != "nan")]

    pre = d[(d["ts"] >= PRE0) & (d["ts"] < EVENT)]
    post = d[(d["ts"] >= EVENT) & (d["ts"] <= POST1)]

    # ------------------------------------------------------- 1. price ranges
    sep("1. Price distributions -- do Cannazon's prices sit in Apollon's range?")
    pos = d[d["price"] > 0]
    log("  median / IQR of positive prices, per market (same units as the dump):")
    for m in MARKETS:
        p = pos.loc[pos["market"] == m, "price"]
        if len(p) < 100:
            continue
        log("    %-11s n=%-7d median=%.6g  IQR=%.6g..%.6g  p90=%.6g"
            % (m, len(p), p.median(), p.quantile(.25), p.quantile(.75),
               p.quantile(.90)))
    ap = pos.loc[pos["market"] == "Apollon", "price"]
    lo, hi = ap.quantile(.05), ap.quantile(.95)
    log("")
    log("  Apollon's 5th-95th percentile band: %.6g .. %.6g" % (lo, hi))
    for m in ["Cryptonia", "Cannazon"]:
        p = pos.loc[pos["market"] == m, "price"]
        if not len(p):
            continue
        inside = float(((p >= lo) & (p <= hi)).mean())
        log("    %-11s share of reviews inside that band: %.1f%%" % (m, 100 * inside))
        R.setdefault("price_overlap", {})[m] = inside
    log("")
    log("  If both markets overlap Apollon's band about equally, price range does")
    log("  NOT explain why one population moved and the other did not.")

    # ------------------------------------- 2. who entered, by price and rating
    sep("2. Among Apollon-naive sellers, does entry track price or rating?")
    apollon_pre = set(pre.loc[pre["market"] == "Apollon", "vendor"])
    apollon_post = set(post.loc[post["market"] == "Apollon", "vendor"])
    for src in ["Cryptonia", "Cannazon"]:
        s = set(pre.loc[pre["market"] == src, "vendor"]) - apollon_pre
        ent = s & apollon_post
        non = s - apollon_post
        sp = pos[(pos["vendor"].isin(s)) & (pos["market"] == src)]
        gp = sp[sp["vendor"].isin(ent)]["price"]
        np_ = sp[sp["vendor"].isin(non)]["price"]
        log("")
        log("  %s-only sellers naive to Apollon: %d entered, %d did not"
            % (src, len(ent), len(non)))
        log("    median price among entrants : %s"
            % ("%.6g (n=%d)" % (gp.median(), len(gp)) if len(gp) else "n/a"))
        log("    median price among non-entr.: %s"
            % ("%.6g (n=%d)" % (np_.median(), len(np_)) if len(np_) else "n/a"))
        # activity level: is non-entry just a size effect?
        act = pre[pre["market"] == src].groupby("vendor").size()
        a_e = act.reindex(list(ent)).dropna()
        a_n = act.reindex(list(non)).dropna()
        log("    pre-period reviews in %s, entrants : median %.0f (n=%d)"
            % (src, a_e.median() if len(a_e) else float("nan"), len(a_e)))
        log("    pre-period reviews in %s, non-entr.: median %.0f (n=%d)"
            % (src, a_n.median() if len(a_n) else float("nan"), len(a_n)))
        r_e = pre[(pre["vendor"].isin(ent)) & (pre["market"] == src)]["f3n"].mean()
        r_n = pre[(pre["vendor"].isin(non)) & (pre["market"] == src)]["f3n"].mean()
        log("    mean f3 (rating proxy), entrants %.3f vs non-entrants %.3f"
            % (r_e, r_n))
        R.setdefault("entry_profile", {})[src] = {
            "entrants": len(ent), "non_entrants": len(non),
            "median_reviews_entrants": float(a_e.median()) if len(a_e) else None,
            "median_reviews_non": float(a_n.median()) if len(a_n) else None}
        log("    -> if entrants and non-entrants are the same size and the same")
        log("       price, non-entry is not a size or quality effect.")

    # ------------------------- 3. did non-entrants simply stop trading anywhere?
    sep("3. What happened to the sellers who did NOT enter Apollon?")
    log("  Total reviews written in ANY of the five markets, pre vs post, among")
    log("  sellers who were Apollon-naive and active in one dead market.")
    rows = []
    for src in ["Cryptonia", "Cannazon"]:
        s = set(pre.loc[pre["market"] == src, "vendor"]) - apollon_pre
        for lbl, grp in (("entered Apollon", s & apollon_post),
                         ("did NOT enter", s - apollon_post)):
            pp = post[post["vendor"].isin(grp)]
            a_pre = pre[pre["vendor"].isin(grp)]
            rows.append({
                "source": src, "group": lbl, "n": len(grp),
                "pre_reviews": len(a_pre), "post_reviews": len(pp),
                "pre_per_seller": len(a_pre) / max(len(grp), 1),
                "post_per_seller": len(pp) / max(len(grp), 1),
                "still_active_pct": 100.0 * pp["vendor"].nunique() / max(len(grp), 1),
                "post_markets": ", ".join(
                    "%s:%d" % (m, n) for m, n in
                    pp["market"].value_counts().head(4).items()),
            })
    t = pd.DataFrame(rows)
    log("")
    log(t.to_string(index=False))
    R["fate"] = t.to_dict("records")
    log("")
    log("  The column that answers the question is `still_active_pct`: the share of")
    log("  each group still writing reviews anywhere in the ecosystem afterwards.")
    log("  If Cannazon's non-entrants went quiet entirely while Cryptonia's stayed")
    log("  active in Apollon, then the difference between the two markets is not")
    log("  that one population was more mobile -- it is that one had somewhere to")
    log("  go and the other did not.")

    # ------------------------------------------------ 4. f3, what is it?
    sep("4. What is f3?")
    log("  f3 values overall: %s" % dict(d["f3n"].value_counts().head(6)))
    log("  f3 == 1 share by market:")
    for m in MARKETS:
        g = d.loc[d["market"] == m, "f3n"]
        if not len(g):
            continue
        log("    %-11s n=%-7d mean=%.3f  share(==1)=%.1f%%  share(==-1)=%.1f%%"
            % (m, len(g), g.mean(), 100.0 * (g == 1).mean(), 100.0 * (g == -1).mean()))
    log("  -> treated as a rating proxy only if the polarity is defensible; it is")
    log("     reported, not relied on.")

    # ---------------------------------- 5. the untested hypothesis, stated
    sep("5. What this did NOT test")
    log("  The product-overlap explanation -- Cryptonia was a general market and")
    log("  Apollon was general, so its sellers could redeploy, while Cannazon was a")
    log("  cannabis specialist with nowhere comparable to go -- is consistent with")
    log("  everything above and is NOT tested by any of it. The Kilos table has no")
    log("  category column; `price` is a weak and confounded stand-in for product")
    log("  type, and a price band that both markets share says only that both sold")
    log("  things at similar prices.")
    R["untested"] = ("product-category overlap between markets; no category column "
                     "exists in kilos_reviews")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "17_E1_products.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    with open(os.path.join(RESULTS, "17_E1_products.json"), "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, default=str)
    log("\nwrote %s/17_E1_products.{txt,json}" % RESULTS)
    log("E1_PRODUCTS_DONE")


if __name__ == "__main__":
    main()
