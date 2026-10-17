#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""31_E7inf_robust.py -- does E7-inf survive its own outliers, and what
structural features predict resilience?

30_ produced two numbers that a handful of domains could manufacture:

  * reconstitution: 24.93% of removals are followed by a new URL on the same
    host within 7 days. But one host carries 853 URLs, and a host with 853
    URLs will land within 7 days of SOME addition almost by construction.
  * the within-host paired test: 8,552 hosts, but a bulk host contributes
    hundreds of the URLs and one observation.

Neither result is trustworthy until the bulk hosts are removed and the
numbers hold. So parts 1-2 are adversarial to my own results.

Part 3 asks the question the host-level measure cannot: a takedown removes a
HOST. Does the OPERATOR come back under a different host on the same
infrastructure provider? `x.duckdns.org` dying is one event; `y.duckdns.org`
appearing two days later on the same provider is displacement, and that is a
resilience property of the ecosystem rather than of a single host. The
registrable suffix (last two labels; /24 for IP literals) is the provider.
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
_L: list[str] = []

IPV4 = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


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


def suffix_of(h):
    """Registrable-ish provider: last two labels, or the /24 for an IP."""
    if IPV4.match(h):
        return ".".join(h.split(".")[:3]) + ".0/24"
    parts = h.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else h


def recon_rate(rm, add_by_host, W):
    """Removals followed by a new addition on the same host within W days."""
    hit = 0
    for lo_t, h in zip(rm["lo"].to_numpy(), rm["host"].to_numpy()):
        arr = add_by_host.get(h)
        if arr is None:
            continue
        j = np.searchsorted(arr, lo_t, side="right")
        if j < len(arr) and (arr[j] - lo_t) / np.timedelta64(1, "D") <= W:
            hit += 1
    return hit, len(rm)


def main():
    log("=" * 78)
    log("31  E7-inf robustness and structural features")
    log("=" * 78)

    u = read_abusech(os.path.join(RECON, "urlhaus_full__csv.txt"))
    u["added"] = pd.to_datetime(u["dateadded"], errors="coerce")
    u["lo"] = pd.to_datetime(u["last_online"].astype(str).str.strip(),
                             errors="coerce")
    u["offline"] = (u["url_status"].astype(str).str.strip() == "offline")
    u["host"] = u["url"].map(host_of)
    u["suffix"] = u["host"].map(suffix_of)
    coh = u[u["added"] >= CUT].copy()
    log("\n  cohort (added >= %s): %d rows, %d hosts"
        % (CUT.date(), len(coh), int(coh["host"].nunique())))

    sep("1. Composition -- what kind of infrastructure is this?")
    coh["is_ip"] = coh["host"].map(lambda h: bool(IPV4.match(h)))
    log("  URLs on IP literals : %d (%.2f%%)"
        % (int(coh["is_ip"].sum()), 100.0 * coh["is_ip"].mean()))
    log("  URLs on named hosts : %d (%.2f%%)"
        % (int((~coh["is_ip"]).sum()), 100.0 * (~coh["is_ip"]).mean()))
    log("")
    log("  top 12 providers by distinct HOSTS (a free-subdomain provider shows")
    log("  up here as many hosts under one suffix):")
    prov = coh.groupby("suffix").agg(hosts=("host", "nunique"),
                                     urls=("host", "size")).sort_values(
        "hosts", ascending=False)
    tot_hosts = coh["host"].nunique()
    for sx, r in prov.head(12).iterrows():
        log("    %-28s hosts=%5d (%5.2f%%) urls=%6d"
            % (sx, r["hosts"], 100.0 * r["hosts"] / tot_hosts, r["urls"]))
    log("  distinct providers: %d" % len(prov))

    sep("2. ★ Adversarial to my own results -- drop the bulk hosts")
    hs = coh.groupby("host").size().sort_values(ascending=False)
    log("  host size distribution: median=%d p90=%d p99=%d max=%d"
        % (hs.median(), hs.quantile(.90), hs.quantile(.99), hs.max()))
    W = 7
    rm_all = coh[coh["offline"] & coh["lo"].notna()].copy()
    log("")
    log("  host-level reconstitution (W=7d) under progressively stricter cuts:")
    log("  %-34s %9s %9s %10s" % ("restriction", "removals", "recon", "rate"))
    for lbl, keep in (
            ("all hosts", hs.index),
            ("drop top 0.1pct of hosts", hs.index[int(np.ceil(.001 * len(hs))):]),
            ("drop top 1pct of hosts", hs.index[int(np.ceil(.01 * len(hs))):]),
            ("drop top 10pct of hosts", hs.index[int(np.ceil(.10 * len(hs))):]),
            ("hosts with <=5 URLs", hs[hs <= 5].index),
            ("hosts with <=2 URLs", hs[hs <= 2].index)):
        keep = pd.Index(keep)
        sub_coh = coh[coh["host"].isin(keep)]
        ab = {h: np.sort(g["added"].to_numpy()) for h, g in sub_coh.groupby("host")}
        rm = rm_all[rm_all["host"].isin(keep)]
        rm = rm[(SNAP - rm["lo"]).dt.total_seconds() / 86400.0 >= W]
        if len(rm) == 0:
            continue
        hit, n = recon_rate(rm, ab, W)
        log("  %-34s %9d %9d %9.2f%%" % (lbl, n, hit, 100.0 * hit / n))

    log("")
    log("  within-host paired test under the same cuts:")
    log("  %-34s %8s %10s %10s %10s"
        % ("restriction", "hosts", "first", "later", "diff"))
    for lbl, keep in (
            ("all multi-URL hosts", None),
            ("drop top 1pct of hosts", hs.index[int(np.ceil(.01 * len(hs))):]),
            ("hosts with <=5 URLs", hs[hs <= 5].index),
            ("hosts with <=2 URLs", hs[hs <= 2].index)):
        keep = hs.index if keep is None else pd.Index(keep)
        c2 = coh[coh["host"].isin(keep)].sort_values(["host", "added"]).copy()
        c2["rank"] = c2.groupby("host").cumcount()
        c2["nsib"] = c2.groupby("host")["added"].transform("size")
        mh = c2[c2["nsib"] >= 2]
        H = 7.0
        ok = mh[(SNAP - mh["added"]).dt.total_seconds() / 86400.0 >= H].copy()
        ok["died7"] = (ok["offline"] & ok["lo"].notna()
                       & (((ok["lo"] - ok["added"]).dt.total_seconds() / 86400.0) <= H))
        f = ok[ok["rank"] == 0].set_index("host")["died7"]
        l = ok[ok["rank"] >= 1].groupby("host")["died7"].mean()
        b = pd.concat([f.rename("f"), l.rename("l")], axis=1).dropna()
        if len(b) == 0:
            continue
        d = (b["l"].astype(float) - b["f"].astype(float))
        log("  %-34s %8d %10.4f %10.4f %+10.4f"
            % (lbl, len(b), b["f"].mean(), b["l"].mean(), d.mean()))

    sep("3. ★ Provider-level displacement -- does the operator come back?")
    log("  A takedown removes a HOST. The resilience question is whether the")
    log("  operator reappears as a NEW host under the SAME provider suffix.")
    log("  (Registrable suffix, or /24 for IP literals.)")
    # first-seen time of each host, grouped by provider
    first_seen = coh.groupby(["suffix", "host"])["added"].min().reset_index()
    fs_by_sfx = {s: np.sort(g["added"].to_numpy())
                 for s, g in first_seen.groupby("suffix")}
    rm = rm_all[(SNAP - rm_all["lo"]).dt.total_seconds() / 86400.0 >= 7]
    log("")
    log("  %4s %9s %11s %11s" % ("W", "removals", "new-host", "rate"))
    for W in (1, 3, 7, 30):
        sub = rm_all[(SNAP - rm_all["lo"]).dt.total_seconds() / 86400.0 >= W]
        hit = 0
        for lo_t, sx in zip(sub["lo"].to_numpy(), sub["suffix"].to_numpy()):
            arr = fs_by_sfx.get(sx)
            if arr is None:
                continue
            j = np.searchsorted(arr, lo_t, side="right")
            if j < len(arr) and (arr[j] - lo_t) / np.timedelta64(1, "D") <= W:
                hit += 1
        log("  %4d %9d %11d %10.2f%%" % (W, len(sub), hit, 100.0 * hit / len(sub)))
    log("")
    log("  ★ Compare with the host-level table in section 2: if the provider")
    log("  rate is close to the host rate, the 'new URL' is usually a new HOST")
    log("  (displacement); if it is much lower, the same host is being reused.")
    log("  provider-level rate at W=7 uses %d removals."
        % len(rm))

    sep("4. Placebo for the provider-level measure")
    rng = np.random.default_rng(20260924)
    W = 7
    sub = rm_all[(SNAP - rm_all["lo"]).dt.total_seconds() / 86400.0 >= W]
    real = 0
    for lo_t, sx in zip(sub["lo"].to_numpy(), sub["suffix"].to_numpy()):
        arr = fs_by_sfx.get(sx)
        if arr is None:
            continue
        j = np.searchsorted(arr, lo_t, side="right")
        if j < len(arr) and (arr[j] - lo_t) / np.timedelta64(1, "D") <= W:
            real += 1
    real_rate = 100.0 * real / max(len(sub), 1)
    lo_vals = sub["lo"].to_numpy()
    pl = []
    for _ in range(200):
        perm = rng.permutation(lo_vals)
        hit = 0
        for lo_t, sx in zip(perm, sub["suffix"].to_numpy()):
            arr = fs_by_sfx.get(sx)
            if arr is None:
                continue
            j = np.searchsorted(arr, lo_t, side="right")
            if j < len(arr) and (arr[j] - lo_t) / np.timedelta64(1, "D") <= W:
                hit += 1
        pl.append(100.0 * hit / max(len(sub), 1))
    pl = np.array(pl)
    log("  real provider displacement (W=7d) = %.2f%%" % real_rate)
    log("  placebo (removal times shuffled)  = %.2f%% (sd %.2f), p = %.4f"
        % (pl.mean(), pl.std(), float((pl >= real_rate).mean())))
    log("  ★ As with the host measure, the placebo floor is NOT zero -- a")
    log("  provider with many hosts collects a hit by chance. The effect size is")
    log("  the EXCESS over the placebo, %.2f pp, not the raw rate."
        % (real_rate - pl.mean()))

    out = dict(providers=int(len(prov)),
               ip_url_share=float(coh["is_ip"].mean()),
               host_size=dict(median=float(hs.median()), p99=float(hs.quantile(.99)),
                              max=int(hs.max())),
               provider_disp_7d=float(real_rate),
               provider_placebo=float(pl.mean()),
               provider_excess=float(real_rate - pl.mean()))
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "31_E7inf_robust.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "31_E7inf_robust.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/31_E7inf_robust.{txt,json}" % RESULTS)
    log("E7INF_ROBUST_DONE")


if __name__ == "__main__":
    main()
