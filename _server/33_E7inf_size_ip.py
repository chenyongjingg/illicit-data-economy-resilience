#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""33_E7inf_size_ip.py -- is the named-host signal size, or is it named-ness?

32_ left two cells standing: named hosts (+15.76 pp excess, p<0.005) and
IP-literal hosts (+5.73 pp). But ordinary small hosts showed NO excess
(<=2 URLs: -2.22 pp). If "named host" is just a proxy for "bulk host", the
named-host result is the same size artifact wearing a different label.

The 2x4 table below separates the two: host size bucket crossed with
IP-vs-named, each cell with its own stratum-matched placebo. The question is
whether the named-host excess survives INSIDE a size bucket -- i.e. whether
named hosts with <=2 URLs show excess, where an IP host with <=2 URLs does not.
If it does not survive, nothing here is about naming.
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
NREP = 100
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


def rate_for(lo_vals, hosts, ab, W):
    hit = 0
    for lo_t, h in zip(lo_vals, hosts):
        arr = ab.get(h)
        if arr is None:
            continue
        j = np.searchsorted(arr, lo_t, side="right")
        if j < len(arr) and (arr[j] - lo_t) / np.timedelta64(1, "D") <= W:
            hit += 1
    return hit


def main():
    log("=" * 78)
    log("33  Size x naming: where does the reconstitution excess actually live?")
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
    ab = {h: np.sort(g["added"].to_numpy()) for h, g in coh.groupby("host")}
    ip_of = coh.groupby("host")["is_ip"].first()
    rm_all = coh[coh["offline"] & coh["lo"].notna()].copy()
    rm_all = rm_all[(SNAP - rm_all["lo"]).dt.total_seconds() / 86400.0 >= W]
    log("\n  usable removals: %d" % len(rm_all))

    rng = np.random.default_rng(20260924)
    sep("Excess over a stratum-matched placebo, by size x naming")
    log("  %-6s %-7s %8s %9s %9s %9s %8s"
        % ("size", "kind", "removals", "real%", "floor%", "excess", "p"))
    out = {}
    for lo_s, hi_s, hyp_s, isip in [
            (1, 1, "1", False), (2, 2, "2", False), (3, 5, "3-5", False),
            (6, 20, "6-20", False), (21, 10 ** 9, ">20", False),
            (1, 1, "1", True), (2, 2, "2", True), (3, 5, "3-5", True),
            (6, 20, "6-20", True), (21, 10 ** 9, ">20", True)]:
        hsx = hs[(hs >= lo_s) & (hs <= hi_s)]
        keep = pd.Index([h for h in hsx.index if ip_of.get(h, False) == isip])
        rm = rm_all[rm_all["host"].isin(keep)]
        if len(rm) < 30:
            log("  %-6s %-7s %8d  (too few to test)"
                % (hyp_s, "IP" if isip else "named", len(rm)))
            continue
        sub = {h: ab[h] for h in keep if h in ab}
        lo = rm["lo"].to_numpy()
        hh = rm["host"].to_numpy()
        real = 100.0 * rate_for(lo, hh, sub, W) / len(rm)
        pl = np.array([100.0 * rate_for(rng.permutation(lo), hh, sub, W)
                       / len(rm) for _ in range(NREP)])
        log("  %-6s %-7s %8d %9.2f %9.2f %+9.2f %8.3f"
            % (hyp_s, "IP" if isip else "named", len(rm), real, pl.mean(),
               real - pl.mean(), float((pl >= real).mean())))
        out["%s_%s" % (hyp_s, "ip" if isip else "named")] = dict(
            n=int(len(rm)), real=real, floor=float(pl.mean()),
            excess=real - float(pl.mean()), p=float((pl >= real).mean()))

    sep("Reading")
    log("  The two size-1 rows are the negative control: a host with ONE URL")
    log("  cannot have a later addition, so real must be exactly 0.00% in both.")
    log("  If named-1 and IP-1 both read 0.00%, the machinery leaks nothing, and")
    log("  any excess that appears in the larger buckets is real pairing signal")
    log("  rather than an artefact of the shuffle.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "33_E7inf_size_ip.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "33_E7inf_size_ip.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/33_E7inf_size_ip.{txt,json}" % RESULTS)
    log("SIZE_IP_DONE")


if __name__ == "__main__":
    main()
