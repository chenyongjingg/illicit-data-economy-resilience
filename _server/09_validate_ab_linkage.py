#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""09_validate_ab_linkage.py -- can AlphaBay support a survival analysis at all?

`ab_items` carries `tenure_days` and `censored`, which looks like a ready-made
survival frame. It is not: `censored` is True for all 114,231 rows, so there are
ZERO events and no Kaplan-Meier curve can be estimated from it. `tenure_days` is
only the age of a listing at the scrape date -- a backward recurrence time, which
is length-biased by construction: long-lived listings are over-represented simply
because they existed when the scraper ran.

The salvageable outcome is time from listing to the item's FIRST feedback event,
which `ab_feedback` timestamps. That is a real time-to-event with real censoring.
But it is only usable if three things hold, and none may be assumed:

  1. `item_number` in the feedback file refers to the same entity as `item_number`
     in the items file (not, say, a vendor id in a different namespace);
  2. feedback timestamps fall AFTER the listing date (a link whose "event"
     precedes its own origin is a broken join);
  3. `n_feedback` in the items file actually counts the feedback rows present.

This script tests all three before E4 is written.

Output: results/09_ab_linkage.txt
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

WORK = "/root/cis/work"
RESULTS = "/root/cis/results"
_L: list[str] = []


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
    items = pd.read_parquet(os.path.join(WORK, "ab_items.parquet"))
    fb = pd.read_parquet(os.path.join(WORK, "ab_feedback.parquet"))
    SCRAPE = pd.Timestamp("2017-01-28")

    sep("0. The frame that cannot work, stated first")
    log("  ab_items rows: %d ; censored=True in %d (%.1f%%) ; events: %d"
        % (len(items), int(items["censored"].sum()),
           100.0 * items["censored"].mean(), int((~items["censored"]).sum())))
    log("  -> `tenure_days` has NO events behind it. It is the age of a listing at")
    log("     the scrape date, i.e. a backward recurrence time, and it is")
    log("     length-biased: an item that lived longer is likelier to be in the")
    log("     dump. A KM curve fitted to it would be estimating nothing.")
    log("  `tenure_days`: %s" % dict(items["tenure_days"].describe(
        percentiles=[.25, .5, .75, .9]).round(1)))

    # ------------------------------------------------ 1. does the key join?
    sep("1. Does `item_number` mean the same thing in both files?")
    fbi = fb["item_number"].dropna().astype("int64")
    log("  items:    %d rows, %d distinct item_number, range %d..%d"
        % (len(items), items["item_number"].nunique(),
           items["item_number"].min(), items["item_number"].max()))
    log("  feedback: %d rows, %d distinct item_number, range %d..%d"
        % (len(fb), fbi.nunique(), fbi.min(), fbi.max()))
    inter = set(items["item_number"]) & set(fbi)
    log("  intersection: %d of %d items (%.1f%%)"
        % (len(inter), len(items), 100.0 * len(inter) / len(items)))

    # ---------------------------------------------- 2. does n_feedback agree?
    sep("2. Does `n_feedback` count the feedback rows that are actually present?")
    cnt = fbi.value_counts()
    it = items[["item_number", "n_feedback", "sold", "listed_date"]].copy()
    it["fb_rows"] = it["item_number"].map(cnt).fillna(0).astype(int)
    it["has_fb"] = it["fb_rows"] > 0
    log("  items with n_feedback==0: %d ; with no feedback rows: %d"
        % (int((it["n_feedback"] == 0).sum()), int((~it["has_fb"]).sum())))
    log("  (n_feedback==0) XOR (has no rows): %d  <-- must be 0 for a clean link"
        % int(((it["n_feedback"] == 0) ^ (~it["has_fb"])).sum()))
    both = it[it["has_fb"] & (it["n_feedback"] > 0)]
    agree = int((both["n_feedback"] == both["fb_rows"]).sum())
    log("  where both nonzero: exact match %d/%d (%.1f%%)"
        % (agree, len(both), 100.0 * agree / max(len(both), 1)))
    d = (both["fb_rows"] - both["n_feedback"])
    log("  difference (rows - n_feedback): mean=%.3f median=%.1f p95=%.1f min=%d max=%d"
        % (d.mean(), d.median(), d.quantile(.95), d.min(), d.max()))
    log("  crosstab n_feedback==0 vs has rows:")
    log(pd.crosstab(it["n_feedback"] == 0, it["has_fb"]).to_string())

    # ------------------------------------------------------- 3. time order
    sep("3. Do feedback events fall after the listing date?")
    first = fb.groupby("item_number")["ts"].min().rename("first_fb")
    last = fb.groupby("item_number")["ts"].max().rename("last_fb")
    j = it.set_index("item_number").join(first).join(last).dropna(subset=["first_fb"])
    j["t_first"] = (j["first_fb"] - j["listed_date"]).dt.total_seconds() / 86400.0
    j["t_last"] = (j["last_fb"] - j["listed_date"]).dt.total_seconds() / 86400.0
    log("  joined items: %d" % len(j))
    log("  days from listing to FIRST feedback: %s"
        % dict(j["t_first"].describe(percentiles=[.1, .25, .5, .75, .9]).round(2)))
    neg = int((j["t_first"] < 0).sum())
    log("  NEGATIVE (feedback before listing): %d (%.1f%%)"
        % (neg, 100.0 * neg / len(j)))
    if neg:
        log("    if this were large the join would be broken -- item_number would")
        log("    not refer to the same entity. Inspect:")
        log(j[j["t_first"] < 0][["listed_date", "first_fb", "t_first"]].head(5).to_string())

    # ------------------------------------------------------- 4. censoring
    sep("4. The outcome E4 can actually use")
    it["event"] = it["has_fb"]
    it["duration"] = np.where(
        it["event"],
        it["item_number"].map((first - it.set_index("item_number")["listed_date"])
                              .dt.total_seconds() / 86400.0).astype(float),
        (SCRAPE - it["listed_date"]).dt.total_seconds() / 86400.0)
    bad = it["duration"].isna() | (it["duration"] < 0)
    log("  definition: duration = days from `listed_date` to the FIRST feedback")
    log("              event; items with no feedback are censored at the scrape")
    log("              date %s." % SCRAPE.date())
    log("  n=%d  events=%d (%.1f%%)  censored=%d"
        % (len(it), int(it["event"].sum()), 100.0 * it["event"].mean(),
           int((~it["event"]).sum())))
    log("  rows with missing/negative duration: %d" % int(bad.sum()))
    ok = it[~bad]
    log("  duration (days): %s" % dict(ok["duration"].describe(
        percentiles=[.25, .5, .75, .9]).round(2)))
    log("")
    log("  `sold` is a COUNT of units, not a flag: %s"
        % dict(it["sold"].describe(percentiles=[.5, .9, .99]).round(1)))
    log("  has_fb (rows) vs sold>0 (units moved) -- these need NOT agree, since a")
    log("  buyer may receive goods without leaving feedback:")
    log(pd.crosstab(it["has_fb"], it["sold"] > 0).to_string())
    log("  -> `sold` is an outcome but it carries no timestamp, so it can inform")
    log("     whether an item ever moved, never when.")

    # ---------------------------------------------------- 5. other markets
    sep("5. Do the other markets carry time at all?")
    ks = pd.read_parquet(os.path.join(WORK, "kilos_reviews.parquet"))
    f2 = pd.to_numeric(ks["f2"], errors="coerce")
    as_ts = pd.to_datetime(f2, unit="s", errors="coerce")
    good = as_ts[(as_ts > "2010-01-01") & (as_ts < "2030-01-01")]
    log("  kilos_reviews.f2 as unix seconds: parseable=%d/%d"
        % (int(f2.notna().sum()), len(ks)))
    log("    plausible dates: %d ; span %s .. %s"
        % (len(good), good.min(), good.max()))
    log("    f2 values: %s" % dict(f2.value_counts().head(5)))
    log("    by market: %s" % dict(ks["market"].value_counts()))
    # One "market" label is a leaked review body, not a market name -- the same
    # class of row as the 'rating' value in ab_feedback.
    odd = [m for m in ks["market"].unique() if len(str(m)) > 24 or "\n" in str(m)]
    log("    !! non-market labels in the market column: %s"
        % [str(m)[:60] for m in odd])
    mk = pd.DataFrame({"m": ks["market"], "ts": as_ts}).dropna()
    log("    markets with a plausible date (n, span):")
    for m, g in mk.groupby("m"):
        log("      %-14s n=%-7d %s .. %s" % (str(m)[:14], len(g),
                                             g["ts"].min().date(), g["ts"].max().date()))
    hs = pd.read_parquet(os.path.join(WORK, "hansa_reviews.parquet"))
    log("")
    log("  hansa: review_ts span %s .. %s ; scrape_ts span %s .. %s"
        % (hs["review_ts"].min(), hs["review_ts"].max(),
           hs["scrape_ts"].min(), hs["scrape_ts"].max()))
    log("    distinct items: %d ; reviews/item median=%.0f max=%d"
        % (hs["item_id"].nunique(), hs.groupby("item_id").size().median(),
           hs.groupby("item_id").size().max()))
    log("    vendor names masked in %.1f%% of rows"
        % (100.0 * hs["vendor_masked"].mean()))
    va = pd.read_parquet(os.path.join(WORK, "valhalla_listings.parquet"))
    log("")
    log("  valhalla: %d rows, columns %s -- no date column: %s"
        % (len(va), list(va.columns),
           [c for c in va.columns if "date" in c.lower() or "ts" in c.lower()] or "none"))

    # -------------------------------------------------- 6. feedback hygiene
    sep("6. Feedback-stream hygiene flags")
    r = fb["rating"].value_counts()
    log("  rating values: %s" % dict(r))
    if "rating" in r.index:
        log("  !! the literal string 'rating' appears %d time(s) as a value -- a"
            % int(r["rating"]))
        log("     header row leaked into the data. Locate and exclude it:")
        log(fb[fb["rating"] == "rating"].head(3).to_string())
    log("  ts span: %s .. %s" % (fb["ts"].min(), fb["ts"].max()))
    log("  rows with ts after the scrape date %s: %d"
        % (SCRAPE.date(), int((fb["ts"] > SCRAPE).sum())))

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "09_ab_linkage.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/09_ab_linkage.txt" % RESULTS)
    log("AB_LINKAGE_DONE")


if __name__ == "__main__":
    sys.exit(main())
