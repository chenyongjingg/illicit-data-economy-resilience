#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""23_elliptic_design_probe.py -- the facts that decide whether an address
survival design is identifiable at all.

22_ verified that the row count in wallets_features is a per-(address, time step)
transaction count (98.90% cell agreement against the independently built edge
lists; the 920,691 cells are the same set in both files). The measurement floor
is therefore solid. What is not yet established is whether a *survival* design
sits on top of it, and there are four specific ways it might not:

  1. THE CEILING. An address entering at step t0 can survive at most 49 - t0
     steps. If entry steps are spread out, duration is mechanically determined
     by entry time and any "who survives longer" comparison must condition on
     t0 or it is measuring the calendar.
  2. THE FLOOR. If most addresses appear in exactly one time step, the median
     duration is 0 and a hazard model is fitting the one-shot majority, not
     persistence.
  3. THE ANOMALY. 19_ reported that illicit addresses have a median first step
     of 28 and a median last step of 28, against 22/23 for licit. Both medians
     landing on the same non-central value is the signature of a spike, and a
     spike in the *entry* distribution for one class would generate a spurious
     class difference in any duration model. It has to be looked at directly.
  4. THE WINDOW. Durations in time steps are integers in 0..48 resolution. Real
     Bitcoin block heights are available and are finer. Which clock to use is a
     design decision that needs the actual ranges.

Descriptive only. No model is fitted here.
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


NAMES = {1: "illicit", 2: "licit", 3: "unknown"}


def main():
    log("=" * 78)
    log("Elliptic++: design probe for an address persistence analysis")
    log("=" * 78)

    wf = pd.read_csv(os.path.join(ACT, "wallets_features.csv"), usecols=[
        "address", "Time step", "total_txs", "num_txs_as_sender",
        "num_txs_as receiver", "first_block_appeared_in",
        "last_block_appeared_in", "lifetime_in_blocks",
        "num_timesteps_appeared_in"], low_memory=False)
    wc = pd.read_csv(os.path.join(ACT, "wallets_classes.csv"))

    sep("1. The clock -- what do the block heights actually span?")
    a = wf.groupby("address").agg(
        t0=("Time step", "min"), t1=("Time step", "max"),
        n_steps=("num_timesteps_appeared_in", "first"),
        n_tx=("total_txs", "first"),
        n_sent=("num_txs_as_sender", "first"),
        n_recv=("num_txs_as receiver", "first"),
        fb=("first_block_appeared_in", "first"),
        lb=("last_block_appeared_in", "first"),
        life=("lifetime_in_blocks", "first"))
    a = a.join(wc.set_index("address")["class"])
    log("  first_block_appeared_in: min=%d p50=%.0f p99=%.0f max=%d"
        % (a["fb"].min(), a["fb"].median(), a["fb"].quantile(.99), a["fb"].max()))
    log("  last_block_appeared_in:  min=%d p50=%.0f p99=%.0f max=%d"
        % (a["lb"].min(), a["lb"].median(), a["lb"].quantile(.99), a["lb"].max()))
    log("  block span of the whole dataset: %d blocks"
        % (a["lb"].max() - a["fb"].min()))
    log("  lifetime_in_blocks: p50=%.0f p90=%.0f p99=%.0f max=%d"
        % (a["life"].median(), a["life"].quantile(.90), a["life"].quantile(.99),
           a["life"].max()))
    log("  consistency: lifetime == last-first in %d / %d addresses (%.4f%%)"
        % (int((a["life"] == a["lb"] - a["fb"]).sum()), len(a),
           100.0 * (a["life"] == a["lb"] - a["fb"]).mean()))
    log("  time steps per block: %.1f blocks/step"
        % ((a["lb"].max() - a["fb"].min()) / 48.0))

    sep("2. THE FLOOR -- how many addresses appear in only one time step?")
    log("  %-9s %8s %8s %8s %8s %8s %8s"
        % ("class", "n", "mean", "p25", "p50", "p75", "p90"))
    for k in (1, 2, 3):
        g = a[a["class"] == k]["n_steps"]
        log("  %-9s %8d %8.3f %8.0f %8.0f %8.0f %8.0f"
            % (NAMES[k], len(g), g.mean(), g.quantile(.25), g.quantile(.50),
               g.quantile(.75), g.quantile(.90)))
    log("")
    log("  share appearing in exactly 1 time step, by class:")
    for k in (1, 2, 3):
        g = a[a["class"] == k]["n_steps"]
        log("    %-9s %6.2f%%   (>=2 steps: %.2f%%)"
            % (NAMES[k], 100.0 * (g == 1).mean(), 100.0 * (g >= 2).mean()))

    sep("3. THE ANOMALY -- where do illicit addresses actually sit in time?")
    log("  entry step t0 distribution, share per step (1..49), by class:")
    log("  %5s %9s %9s %9s" % ("step", "illicit", "licit", "unknown"))
    for t in range(1, 50):
        row = []
        for k in (1, 2, 3):
            g = a[a["class"] == k]
            row.append(100.0 * (g["t0"] == t).mean())
        if t <= 12 or t % 4 == 0 or t >= 45:
            log("  %5d %8.2f%% %8.2f%% %8.2f%%" % (t, row[0], row[1], row[2]))
    log("")
    log("  last step t1 distribution, share per step, by class:")
    log("  %5s %9s %9s %9s" % ("step", "illicit", "licit", "unknown"))
    for t in range(1, 50):
        row = []
        for k in (1, 2, 3):
            g = a[a["class"] == k]
            row.append(100.0 * (g["t1"] == t).mean())
        if t <= 12 or t % 4 == 0 or t >= 45:
            log("  %5d %8.2f%% %8.2f%% %8.2f%%" % (t, row[0], row[1], row[2]))
    log("")
    log("  top 6 entry steps by illicit share:")
    sh = a[a["class"] == 1]["t0"].value_counts(normalize=True).head(6) * 100
    log(sh.round(2).to_string())

    sep("4. THE CEILING -- censoring and the entry-step problem")
    cen = a["t1"] == 49
    log("  addresses whose last step is 49 (right-censored): %d (%.2f%%)"
        % (int(cen.sum()), 100.0 * cen.mean()))
    for k in (1, 2, 3):
        g = a[a["class"] == k]
        log("    %-9s censored %7d / %7d = %6.2f%%"
            % (NAMES[k], int((g["t1"] == 49).sum()), len(g),
               100.0 * (g["t1"] == 49).mean()))
    log("")
    log("  ceiling check -- mean available room (49 - t0) by entry decade:")
    for lo in range(1, 50, 10):
        hi = min(lo + 9, 49)
        g = a[(a["t0"] >= lo) & (a["t0"] <= hi)]
        if len(g):
            log("    t0 in %2d..%2d : n=%7d mean(49-t0)=%5.1f  observed mean"
                " duration=%.2f  censored=%.1f%%"
                % (lo, hi, len(g), (49 - g["t0"]).mean(),
                   (g["t1"] - g["t0"]).mean(), 100.0 * (g["t1"] == 49).mean()))

    sep("5. Duration, the raw outcome (t1 - t0, in steps)")
    for k in (1, 2, 3):
        g = a[a["class"] == k]["t1"] - a[a["class"] == k]["t0"]
        log("  %-9s mean=%6.3f p50=%.0f p75=%.0f p90=%.0f p99=%.0f max=%d"
            % (NAMES[k], g.mean(), g.quantile(.50), g.quantile(.75),
               g.quantile(.90), g.quantile(.99), g.max()))
    log("")
    log("  duration in BLOCKS (last-first), by class, for comparability:")
    for k in (1, 2, 3):
        g = a[a["class"] == k]["life"] / 144.0  # 144 blocks/day
        log("  %-9s mean=%7.2f p50=%.1f p90=%.0f (days; 144 blocks/day)"
            % (NAMES[k], g.mean(), g.median(), g.quantile(.90)))

    sep("6. Does class even separate on the raw outcome? (no controls yet)")
    for k in (1, 2, 3):
        for j in (2, 3):
            if k >= j:
                continue
            g1 = a[a["class"] == k]
            g2 = a[a["class"] == j]
            m1 = (g1["t1"] - g1["t0"]).mean()
            m2 = (g2["t1"] - g2["t0"]).mean()
            log("  mean duration %s=%.3f vs %s=%.3f  (diff %+.3f)"
                % (NAMES[k], m1, NAMES[j], m2, m1 - m2))
    log("")
    log("  ★ these are UNCONDITIONAL. They do not control for entry step, size,")
    log("  or the composition of the labelled subgraph. Reported as a starting")
    log("  point only -- 19_'s 22/23-vs-28 spread is exactly the kind of thing")
    log("  that makes an unconditional comparison misleading.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "23_elliptic_design.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")

    a.to_parquet(os.path.join(RESULTS, "elliptic_address_level.parquet"))
    log("\nwrote %s/23_elliptic_design.txt and elliptic_address_level.parquet"
        % RESULTS)
    log("ELLIPTIC_DESIGN_DONE")


if __name__ == "__main__":
    main()
