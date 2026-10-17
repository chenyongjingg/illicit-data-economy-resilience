#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""32_E7inf_strat_placebo.py -- does the residual reconstitution beat chance?

31_ showed the host-level reconstitution rate is mostly manufactured by bulk
hosts: 21.95% over all hosts, but 6.15% once hosts with more than 2 URLs are
dropped. 30_'s placebo floor was 15.76%, i.e. ABOVE the residual 6.15% -- which
would mean the residual is not merely weak but below chance, and the whole
host-level measure is an artefact of host size.

That comparison is not clean, though: 30_'s placebo ran on the multi-URL-host
set. The floor must be recomputed inside each stratum, on the same hosts, the
same additions and the same number of removals, with only the pairing broken.

So this script reports, for each stratum:
    real rate, placebo floor (mean over 200 shuffles), excess, and p
and the verdict is the EXCESS, not the raw rate. A stratum whose excess is
indistinguishable from 0 has no reconstitution signal at all, whatever its raw
rate looks like.
"""
from __future__ import annotations

import io
import json
import os
import re
from urllib.parse import urlparse

import numpy as np
import pandas as pd

RECON = "/root/cis/data/_recon/abusech"
RESULTS = "/root/cis/results"
SNAP = pd.to_datetime("2026-09-23 15:43:18")
CUT = pd.to_datetime("2026-06-25")
W = 7.0
NREP = 200
IPV4 = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
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
    cols = [c.strip().strip('"') for c in header.split(",")]
    return pd.read_csv(io.StringIO("".join(lines[hdr_i + 1:])), header=None,
                       names=cols, low_memory=False, skipinitialspace=True)


def host_of(u):
    try:
        h = urlparse(str(u)).netloc.lower()
    except Exception:  # noqa: BLE001
        return ""
    if "@" in h:
        h = h.split("@")[-1]
    if ":" in h:
        h = h.split(":")[0]
    return h[4:] if h.startswith("www.") else h


def rate_for(lo_vals, hosts, add_by_host, Wd):
    """Fraction of (removal time, host) pairs with an addition in (t, t+W]."""
    hit = 0
    for lo_t, h in zip(lo_vals, hosts):
        arr = add_by_host.get(h)
        if arr is None:
            continue
        j = np.searchsorted(arr, lo_t, side="right")
        if j < len(arr) and (arr[j] - lo_t) / np.timedelta64(1, "D") <= W:
            hit += 1
    return hit


def main():
    log("=" * 78)
    log("32  Reconstitution vs a stratum-matched placebo")
    log("=" * 78)

    u = read_abusech(os.path.join(RECON, "urlhaus_full__csv.txt"))
    u["added"] = pd.to_datetime(u["dateadded"], errors="coerce")
    u["lo"] = pd.to_datetime(u["last_online"].astype(str).str.strip(),
                             errors="coerce")
    u["offline"] = (u["url_status"].astype(str).str.strip() == "offline")
    u["host"] = u["url"].map(host_of)
    u["is_ip"] = u["host"].map(lambda h: bool(IPV4.match(h)))
    coh = u[u["added"] >= CUT].copy()
    hs = coh.groupby("host").size()
    add_by_host_all = {h: np.sort(g["added"].to_numpy())
                       for h, g in coh.groupby("host")}
    rm_all = coh[coh["offline"] & coh["lo"].notna()].copy()
    rm_all = rm_all[(SNAP - rm_all["lo"]).dt.total_seconds() / 86400.0 >= W]
    log("\n  cohort %d rows / %d hosts ; usable removals %d"
        % (len(coh), int(coh["host"].nunique()), len(rm_all)))

    strata = [
        ("all hosts", hs.index),
        ("hosts with <=5 URLs", hs[hs <= 5].index),
        ("hosts with <=2 URLs", hs[hs <= 2].index),
        ("singleton hosts only", hs[hs <= 1].index),
        ("IP-literal hosts", coh[coh["is_ip"]]["host"].unique()),
        ("named hosts", coh[~coh["is_ip"]]["host"].unique()),
    ]

    rng = np.random.default_rng(20260924)
    sep("Stratum-matched placebo (W=7d)")
    log("  %-22s %8s %9s %9s %9s %9s %8s"
        % ("stratum", "removals", "real%", "floor%", "excess", "sd", "p"))
    out = {}
    for lbl, keep in strata:
        keep = pd.Index(keep)
        rm = rm_all[rm_all["host"].isin(keep)]
        if len(rm) == 0:
            continue
        ab = {h: add_by_host_all[h] for h in keep if h in add_by_host_all}
        lo = rm["lo"].to_numpy()
        hh = rm["host"].to_numpy()
        real = 100.0 * rate_for(lo, hh, ab, W) / len(rm)
        pl = np.empty(NREP)
        for i in range(NREP):
            pl[i] = 100.0 * rate_for(rng.permutation(lo), hh, ab, W) / len(rm)
        floor = float(pl.mean())
        exc = real - floor
        p = float((pl >= real).mean())
        log("  %-22s %8d %8.2f %9.2f %+9.2f %9.2f %8.3f"
            % (lbl, len(rm), real, floor, exc, pl.std(), p))
        out[lbl] = dict(n=int(len(rm)), real=real, floor=floor,
                        excess=exc, sd=float(pl.std()), p=p)
        if NREP * len(rm) > 4_000_000:
            log("    (note: this stratum is large; placebo based on %d shuffles)"
                % NREP)

    sep("Verdict rule")
    log("  A stratum is only evidence of reconstitution if its EXCESS is")
    log("  positive and its p is small. A positive raw rate with a matching")
    log("  floor is host size, not displacement.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "32_E7inf_strat_placebo.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "32_E7inf_strat_placebo.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/32_E7inf_strat_placebo.{txt,json}" % RESULTS)
    log("STRAT_PLACEBO_DONE")


if __name__ == "__main__":
    main()
