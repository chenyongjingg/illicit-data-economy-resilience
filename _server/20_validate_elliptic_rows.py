#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""20_validate_elliptic_rows.py -- why does one address have 1,471 rows when the
window is only 49 time steps?

19_ established: 822,942 addresses, 1,268,260 rows, median 1 row/address but max
1,471. It also established that `num_timesteps_appeared_in` equals the row count
for only 71.5% of addresses. The stated value is constant within address (0
addresses disagree with themselves), so the mismatch is about the row count, not
about ambiguity in the stated field.

1,471 > 49. Whatever a row is, "one row per (address, time step) the address was
active in" does not survive that. Three readings remain:

  H1  `address` is not the primary key -- the file is keyed on something finer
      (e.g. address x time step x tx role) and the label join is many-to-one.
  H2  the file contains exact duplicate rows (a bad write, a re-append).
  H3  the file contains rows that are not real observations at all (a leaked
      header, a concatenated second file, a truncated line).

They are distinguishable and the fix differs for each, so the probe tests all
three rather than picking the one that fits the story. In particular H2 vs H1 is
decided by whether whole rows repeat exactly, and H3 by whether the offending
addresses look like addresses at all.
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


def main():
    log("=" * 78)
    log("Elliptic++ actors: what is a row in wallets_features.csv?")
    log("=" * 78)

    wf = pd.read_csv(os.path.join(ACT, "wallets_features.csv"), low_memory=False)
    log("  rows=%d cols=%d" % wf.shape)
    log("  columns: %s" % list(wf.columns))

    sep("H3 first -- are there rows that are not observations?")
    bad = wf[wf["address"] == "address"]
    log("  rows whose address is literally 'address' (leaked header): %d"
        % len(bad))
    a = wf["address"].astype(str)
    log("  address length: min=%d median=%.0f max=%d"
        % (a.str.len().min(), a.str.len().median(), a.str.len().max()))
    log("  address length distribution (head):")
    log(a.str.len().value_counts().sort_index().head(10).to_string())
    # bitcoin addresses are 26-35 chars base58, or 42 for bech32, or 40 hex
    suspicious = wf[(a.str.len() < 26) | (a.str.len() > 42)]
    log("  rows with address length outside 26..42: %d (%.4f%%)"
        % (len(suspicious), 100.0 * len(suspicious) / len(wf)))
    if len(suspicious):
        log("  sample of those addresses: %s"
            % list(suspicious["address"].astype(str).head(8)))

    sep("H2 -- do whole rows repeat exactly?")
    dup_all = int(wf.duplicated().sum())
    log("  exactly duplicated rows (all %d columns): %d" % (wf.shape[1], dup_all))
    dup_key = int(wf.duplicated(subset=["address", "Time step"]).sum())
    log("  duplicated (address, Time step) pairs:  %d" % dup_key)
    log("  distinct (address, Time step) pairs:    %d" % len(
        wf[["address", "Time step"]].drop_duplicates()))
    log("  rows:                                   %d" % len(wf))
    log("")
    log("  If dup_all is large, the file was written more than once and the")
    log("  extra rows are pure duplication. If dup_all is 0 but dup_key is")
    log("  large, the rows differ in some other column -- H1.")

    sep("The extreme addresses")
    per = wf.groupby("address").size().sort_values(ascending=False)
    top = per.head(5)
    log("  top 5 by row count:")
    log(top.to_string())
    for addr in top.index[:3]:
        g = wf[wf["address"] == addr]
        log("")
        log("  --- %s : %d rows ---" % (addr, len(g)))
        log("      distinct Time step: %d ; range %s..%s"
            % (g["Time step"].nunique(), g["Time step"].min(),
               g["Time step"].max()))
        log("      num_timesteps_appeared_in (stated): %s"
            % sorted(g["num_timesteps_appeared_in"].unique()))
        log("      total_txs distinct: %s"
            % sorted(g["total_txs"].unique())[:8])
        log("      num_txs_as_sender distinct: %s"
            % sorted(g["num_txs_as_sender"].unique())[:8])
        log("      Time step value counts (head):")
        log("      " + g["Time step"].value_counts().sort_index().head(6)
            .to_string().replace("\n", "\n      "))

    sep("H1 -- do the counting columns vary within an address?")
    for c in ["total_txs", "num_txs_as_sender", "num_txs_as receiver",
              "Time step"]:
        nu = wf.groupby("address")[c].nunique()
        log("  %-24s varies within address in %7d / %d addresses (%.2f%%)"
            % (c, int((nu > 1).sum()), len(nu), 100.0 * (nu > 1).mean()))
    log("")
    log("  If `total_txs` is constant within address, it is an address-level")
    log("  lifetime total repeated on every row. If it varies, each row carries")
    log("  that step's own count -- which is what a per-step panel needs.")

    sep("Is `total_txs` the sum over steps?")
    const_t = wf.groupby("address")["total_txs"].first()
    nsteps = wf.groupby("address").size()
    ts_sum = wf.groupby("address")["total_txs"].sum()
    cmp = pd.DataFrame({"stated_total": const_t, "rows": nsteps,
                        "sum_over_rows": ts_sum})
    log("  head:")
    log(cmp.head(8).to_string())
    log("")
    log("  correlation(rows, stated_total) = %.4f" % cmp["rows"].corr(
        cmp["stated_total"]))
    log("  If stated_total = sum over rows, the file is a panel. If")
    log("  stated_total = rows (i.e. each row contributes 1), the 'total_txs'")
    log("  column is actually counting time steps and is mislabelled.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "20_elliptic_rows.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/20_elliptic_rows.txt" % RESULTS)
    log("ELLIPTIC_ROWS_DONE")


if __name__ == "__main__":
    main()
