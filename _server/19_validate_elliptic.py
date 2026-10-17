#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""19_validate_elliptic.py -- is wallets_features one row per address, or per
(address, time step)? Everything downstream depends on the answer.

18_ assumed the features file carried per-time-step columns named
`<quantity>_Time Step`. It has none -- that guess was wrong, and the probe
corrected it. What it has instead is a `Time step` column and exactly 1,268,260
rows, which is the README's "# Nodes (temporal interactions)". The likely reading
is long format: one row per address per time step it was active in.

That reading is attractive because it turns the file into a per-address activity
trajectory over 49 discrete steps -- which is what a persistence analysis needs.
It is also completely unverified. If it is wrong, every "active time steps"
statistic computed from it is meaningless.

So test it, and test the things that would break it:
  * Do addresses repeat? How many rows per address?
  * Is `num_timesteps_appeared_in` equal to the number of rows for that address?
  * Are `first_block_appeared_in` / `last_block_appeared_in` constant within an
    address (address-level) or varying (row-level)?
  * What is the range of `Time step`, and does it match "49 time steps"?

Bounded reads only: the file is 606.5 MB and the questions are answerable from a
handful of columns.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

BASE = "/root/cis/data/EllipticPlusPlus-main"
ACT = os.path.join(BASE, "Actors Dataset")
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


COLS = ["address", "Time step", "num_timesteps_appeared_in", "total_txs",
        "first_block_appeared_in", "last_block_appeared_in",
        "lifetime_in_blocks", "num_txs_as_sender", "num_txs_as receiver"]


def main():
    log("=" * 78)
    log("Elliptic++ actors: validating the shape of wallets_features.csv")
    log("=" * 78)

    wf = pd.read_csv(os.path.join(ACT, "wallets_features.csv"), usecols=COLS,
                     low_memory=False)
    log("  rows read: %d" % len(wf))
    log("  columns:   %s" % list(wf.columns))

    sep("1. Is it long format (address x time step)?")
    n_addr = wf["address"].nunique()
    n_rows = len(wf)
    log("  rows: %d ; distinct addresses: %d ; rows/address = %.4f"
        % (n_rows, n_addr, n_rows / n_addr))
    per = wf.groupby("address").size()
    log("  rows per address: min=%d median=%.0f mean=%.2f p90=%.0f max=%d"
        % (per.min(), per.median(), per.mean(), per.quantile(.90), per.max()))
    log("  rows-per-address distribution (top 8):")
    log(per.value_counts().sort_index().head(8).to_string())
    log("")
    log("  -> if rows/address > 1 with a wide spread, the file is long format.")

    sep("2. Does `num_timesteps_appeared_in` equal the actual row count?")
    stated = wf.groupby("address")["num_timesteps_appeared_in"].nunique()
    log("  addresses where the stated value is not constant within address: %d"
        % int((stated > 1).sum()))
    first = wf.groupby("address")["num_timesteps_appeared_in"].first()
    cmp = pd.DataFrame({"stated": first, "actual_rows": per})
    match = int((cmp["stated"] == cmp["actual_rows"]).sum())
    log("  stated == rows: %d / %d (%.2f%%)"
        % (match, len(cmp), 100.0 * match / len(cmp)))
    diff = (cmp["actual_rows"] - cmp["stated"])
    log("  difference (rows - stated): %s"
        % dict(diff.describe(percentiles=[.5, .9]).round(3)))
    log("")
    log("  This is the decisive check. If the two agree, a row IS one time step")
    log("  of that address and `Time step` is the time index.")

    sep("3. Are first/last block address-level or row-level?")
    for c in ["first_block_appeared_in", "last_block_appeared_in",
              "lifetime_in_blocks"]:
        nu = wf.groupby("address")[c].nunique()
        log("  %-28s distinct-within-address >1 in %d/%d addresses (%.3f%%)"
            % (c, int((nu > 1).sum()), len(nu), 100.0 * (nu > 1).mean()))

    sep("4. Time step range")
    ts = wf["Time step"]
    log("  min=%s max=%s ; distinct=%d" % (ts.min(), ts.max(), ts.nunique()))
    log("  value counts (head):")
    log(ts.value_counts().sort_index().head(6).to_string())
    log("  value counts (tail):")
    log(ts.value_counts().sort_index().tail(6).to_string())
    log("  -> README says 49 time steps.")

    sep("5. Join to the labels")
    wc = pd.read_csv(os.path.join(ACT, "wallets_classes.csv"))
    log("  labelled addresses: %d" % len(wc))
    lab = set(wc["address"])
    present = set(wf["address"])
    log("  addresses in features: %d" % len(present))
    log("  labelled AND in features: %d" % len(lab & present))
    log("  labelled but NOT in features: %d" % len(lab - present))
    log("  in features but unlabelled: %d" % len(present - lab))

    # per-address activity span, for labelled addresses only
    sub = wf[wf["address"].isin(lab)]
    span = sub.groupby("address")["Time step"].agg(["min", "max", "size"])
    span = span.join(wc.set_index("address")["class"])
    log("")
    log("  per-address activity span, by class:")
    log("  %-8s %8s %10s %10s %10s %10s" %
        ("class", "n", "first_med", "last_med", "steps_med", "span_med"))
    for k in sorted(span["class"].dropna().unique()):
        g = span[span["class"] == k]
        log("  %-8s %8d %10.0f %10.0f %10.0f %10.0f"
            % (("illicit" if k == 1 else "licit" if k == 2 else "unknown"),
               len(g), g["min"].median(), g["max"].median(), g["size"].median(),
               (g["max"] - g["min"]).median()))
    log("")
    log("  READ CAREFULLY: `max` here is the last step the address appears in")
    log("  WITHIN the 49-step window. It is not a death time. An address whose")
    log("  observed last step is 49 is censored, not terminated, and an address")
    log("  can be silent for several steps and return.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "19_elliptic_validate.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/19_elliptic_validate.txt" % RESULTS)
    log("ELLIPTIC_VALIDATE_DONE")


if __name__ == "__main__":
    main()
