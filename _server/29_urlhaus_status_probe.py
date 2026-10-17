#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""29_urlhaus_status_probe.py -- is `url_status` a live state or a stale default?

28_ found a HARD structural boundary that the year counts had hidden:

    month      added   offline   %off
    2026-05       81         0    0.0
    2026-06     7293      2423   33.2
    2026-07    15644     15451   98.8

and 0.0% offline for EVERY month before 2026-06 -- including 3,691 rows added
2025-10 and 29 added 2019-01. A URL added in 2019 is not still online. So
`url_status == "online"` on an old row is probably not a claim about the world;
it is the value the field defaults to when nothing has re-checked that row.

If that is so, then 28_'s cohort (everything from 2025-03) is mostly rows whose
`offline = False` is STALE, and they enter the KM curve as long-lived censored
observations -- which is why the 90th percentile came back `nan` and why the
`drop` treatment's median was so much longer than `zero`'s.

THE DECISIVE MEASUREMENT, and it is cheap:
  For rows added before 2026-06, what does `last_online` actually contain?
    * if it is populated and OLD (i.e. <= the addition date, or years stale),
      then those rows are dead and `url_status` is stale for them
    * if it is populated and ~= the snapshot, then the crawler really did see
      them live recently and the flag means something
  Cross-tabulating (added year) x (last_online year) answers this without any
  modelling, and 27_ already established that `last_online` is populated for
  100% of "online" rows, so the field is present to be read.
"""
from __future__ import annotations

import io
import os

import numpy as np
import pandas as pd

RECON = "/root/cis/data/_recon/abusech"
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


def read_abusech(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    hdr_i = None
    for i, ln in enumerate(lines[:40]):
        if not ln.lstrip().startswith("#"):
            continue
        s = ln.lstrip().lstrip("#").strip()
        if s and "," in s:
            hdr_i, header = i, s
            break
    if hdr_i is None:
        raise SystemExit("no header found")
    cols = [c.strip().strip('"') for c in header.split(",")]
    return pd.read_csv(io.StringIO("".join(lines[hdr_i + 1:])), header=None,
                       names=cols, low_memory=False, skipinitialspace=True)


def main():
    log("=" * 78)
    log("29  Is url_status a live state or a stale default?")
    log("=" * 78)
    SNAP = pd.to_datetime("2026-09-23 15:43:18")

    u = read_abusech(os.path.join(RECON, "urlhaus_full__csv.txt"))
    u["added"] = pd.to_datetime(u["dateadded"], errors="coerce")
    u["lo"] = pd.to_datetime(u["last_online"].astype(str).str.strip(),
                             errors="coerce")
    u["offline"] = (u["url_status"].astype(str).str.strip() == "offline")
    log("\n  rows: %d" % len(u))

    CUT = pd.to_datetime("2026-06-01")
    old = u[u["added"] < CUT]
    new = u[u["added"] >= CUT]
    log("  pre-2026-06: %d rows, offline=%d" % (len(old), int(old["offline"].sum())))
    log("  2026-06+   : %d rows, offline=%d" % (len(new), int(new["offline"].sum())))

    sep("1. ★ pre-2026-06 rows: what is in last_online?")
    log("  last_online populated: %d / %d (%.2f%%)"
        % (int(old["lo"].notna().sum()), len(old), 100.0 * old["lo"].notna().mean()))
    for lbl, m in (("url_status == online", ~old["offline"]),
                   ("url_status == offline", old["offline"])):
        g = old[m]
        if len(g) == 0:
            log("  %-22s n=0" % lbl)
            continue
        lo = g["lo"]
        log("  %-22s n=%6d  lo populated=%6d  lo min=%s  lo max=%s"
            % (lbl, len(g), int(lo.notna().sum()),
               lo.min() if lo.notna().any() else None,
               lo.max() if lo.notna().any() else None))

    sep("2. ★ THE DECISIVE TABLE -- added year x last_online year")
    u["ay"] = u["added"].dt.year
    u["ly"] = u["lo"].dt.year
    ct = pd.crosstab(u["ay"], u["ly"].fillna(-1).astype(int), dropna=False)
    log(ct.to_string())
    log("")
    log("  (column -1 = last_online is NaT)")
    log("")
    log("  ★ Read this way: if the OLD added-years' last_online sits in their own")
    log("  year, the crawler simply has not touched them since and `online` is a")
    log("  default, not an observation. If it sits in 2026, they really were seen")
    log("  live recently.")

    sep("3. How stale is last_online, for rows flagged online?")
    on = u[~u["offline"] & u["lo"].notna()].copy()
    on["age_days"] = (SNAP - on["lo"]).dt.total_seconds() / 86400.0
    log("  rows flagged online with a parseable last_online: %d" % len(on))
    log("  days between last_online and the snapshot:")
    log("    min=%.2f p10=%.2f p50=%.2f p90=%.2f max=%.1f"
        % (on["age_days"].min(), on["age_days"].quantile(.10),
           on["age_days"].median(), on["age_days"].quantile(.90),
           on["age_days"].max()))
    for thr, lbl in ((1, "within 1 day of snapshot"),
                     (7, "within 7 days"),
                     (30, "within 30 days"),
                     (365, "within 1 year")):
        log("    %-26s %6d (%.2f%%)"
            % (lbl, int((on["age_days"] <= thr).sum()),
               100.0 * (on["age_days"] <= thr).mean()))
    log("")
    log("  by added-year, share flagged online whose last_online is within 30d")
    log("  of the snapshot (a live-check) vs older (a stale default):")
    for y in sorted(on["ay"].unique()):
        g = on[on["ay"] == y]
        log("    added %d  n=%6d  <=30d: %6.2f%%   >30d: %6.2f%%"
            % (y, len(g), 100.0 * (g["age_days"] <= 30).mean(),
               100.0 * (g["age_days"] > 30).mean()))

    sep("4. Consequence for the cohort")
    live = on[on["age_days"] <= 7]
    log("  rows flagged online AND re-checked within 7d of snapshot: %d" % len(live))
    log("  => these are the only rows where `online` is an observation.")
    log("  every other row must leave the risk set or be re-coded.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "29_urlhaus_status_probe.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/29_urlhaus_status_probe.txt" % RESULTS)
    log("STATUS_PROBE_DONE")


if __name__ == "__main__":
    main()
