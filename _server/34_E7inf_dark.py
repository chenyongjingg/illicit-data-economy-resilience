#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""34_E7inf_dark.py -- reconstitution, but only after the host actually went DARK.

33_ established that the host-level reconstitution excess is zero for 2-URL
hosts and grows with host size. Size alone is not evidence of reconstitution:

    a host with 100 URLs is continuously active, so of course SOME addition
    lands within 7 days of ANY removal time. "Removal followed by an addition"
    is the DEFAULT for a busy host, not a response to a takedown.

The measure so far cannot tell "the operator came back after the takedown" from
"the host never went quiet". This script separates them by asking the question
only of hosts that were FULLY DARK at the moment of removal:

    a darkening event at time t = a removal at t after which the host had NO
    remaining live URL. Every URL added before t is already offline by t.

Only then does a later addition mean the host came back. A host that still had
live URLs at t did not come back -- it never left.

The confound is removed by construction: a continuously-active host has live
URLs at t and so contributes no darkening event at all. The cost is sample
size, which is reported rather than hidden.
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


def main():
    log("=" * 78)
    log("34  Reconstitution after a DARKENING event (host fully offline)")
    log("=" * 78)

    u = read_abusech(os.path.join(RECON, "urlhaus_full__csv.txt"))
    u["added"] = pd.to_datetime(u["dateadded"], errors="coerce")
    u["lo"] = pd.to_datetime(u["last_online"].astype(str).str.strip(),
                             errors="coerce")
    u["offline"] = (u["url_status"].astype(str).str.strip() == "offline")
    u["host"] = u["url"].map(host_of)
    u["is_ip"] = u["host"].map(lambda h: bool(IPV4.match(h)))
    coh = u[u["added"] >= CUT].copy()

    sep("1. Finding darkening events")
    log("  A darkening event at t: a URL goes offline at t AND every URL the")
    log("  host had added before t is already offline by t.")
    dark = []           # (host, t, n_urls_before)
    n_rem = 0
    for h, g in coh.groupby("host"):
        g = g.sort_values("added")
        adds = g["added"].to_numpy()
        off = g["offline"].to_numpy()
        los = g["lo"].to_numpy()
        for i in range(len(g)):
            if not off[i] or np.isnat(los[i]):
                continue
            t = los[i]
            n_rem += 1
            # URLs existing at t (added at or before t)
            prior = adds <= t
            prior[i] = False
            if not prior.any():
                dark.append((h, t, 0))         # its own only URL -> dark
                continue
            # alive at t: online rows, and offline rows whose lo is after t
            alive = (~off[prior]) | (los[prior] > t)
            if not alive.any():
                dark.append((h, t, int(prior.sum())))
    D = pd.DataFrame(dark, columns=["host", "t", "n_prior"])
    log("  removals considered     : %d" % n_rem)
    log("  darkening events        : %d (%.2f%% of removals)"
        % (len(D), 100.0 * len(D) / max(n_rem, 1)))
    log("  hosts with >=1 darkening: %d / %d"
        % (D["host"].nunique(), coh["host"].nunique()))
    log("")
    log("  ★ The other %.2f%% of removals happened while the host still had"
        % (100.0 - 100.0 * len(D) / max(n_rem, 1)))
    log("  live URLs -- those hosts never went quiet, nothing needs explaining.")

    ab = {h: np.sort(g["added"].to_numpy()) for h, g in coh.groupby("host")}

    def hits(tvals, hosts, W):
        c = 0
        for t, h in zip(tvals, hosts):
            arr = ab.get(h)
            if arr is None:
                continue
            j = np.searchsorted(arr, t, side="right")
            if j < len(arr) and (arr[j] - t) / np.timedelta64(1, "D") <= W:
                c += 1
        return c

    sep("2. ★ Does the host come back? (darkening events only)")
    log("  %4s %9s %9s %11s %11s %11s" %
        ("W", "n_used", "returns", "real%", "floor%", "excess"))
    out = {}
    for W in (1, 3, 7, 30):
        sub = D[(SNAP - D["t"]).dt.total_seconds() / 86400.0 >= W]
        if len(sub) == 0:
            continue
        tvals = sub["t"].to_numpy()
        hh = sub["host"].to_numpy()
        real = hits(tvals, hh, W)
        real_pct = 100.0 * real / len(sub)
        rng = np.random.default_rng(20260924)
        pl = np.array([100.0 * hits(rng.permutation(tvals), hh, W) / len(sub)
                       for _ in range(NREP)])
        log("  %4d %9d %9d %10.2f%% %10.2f%% %+10.2f   p=%.3f"
            % (W, len(sub), real, real_pct, pl.mean(),
               real_pct - pl.mean(), float((pl >= real_pct).mean())))
        out["W%d" % W] = dict(n=int(len(sub)), real=real_pct,
                              floor=float(pl.mean()),
                              excess=real_pct - float(pl.mean()),
                              p=float((pl >= real_pct).mean()))

    sep("3. Same thing, by host size and naming")
    log("  %-6s %-7s %9s %11s %11s %11s" %
        ("size", "kind", "n_used", "real%", "floor%", "excess"))
    D2 = D.copy()
    hs = coh.groupby("host").size()
    D2["size"] = D2["host"].map(hs)
    ip_of = coh.groupby("host")["is_ip"].first()
    D2["isip"] = D2["host"].map(ip_of)
    for lab, sel in (
            ("1", D2["size"] == 1), ("2-5", D2["size"].between(2, 5)),
            ("6-20", D2["size"].between(6, 20)), (">20", D2["size"] > 20)):
        for knd, m2 in (("named", ~D2["isip"]), ("IP", D2["isip"])):
            sub = D2[sel & m2]
            sub = sub[(SNAP - sub["t"]).dt.total_seconds() / 86400.0 >= 7]
            if len(sub) < 30:
                log("  %-6s %-7s %9d  (too few)" % (lab, knd, len(sub)))
                continue
            tvals, hh = sub["t"].to_numpy(), sub["host"].to_numpy()
            real_pct = 100.0 * hits(tvals, hh, 7) / len(sub)
            rng = np.random.default_rng(20260924)
            pl = np.array([100.0 * hits(rng.permutation(tvals), hh, 7) / len(sub)
                           for _ in range(NREP)])
            log("  %-6s %-7s %9d %10.2f%% %10.2f%% %+10.2f   p=%.3f"
                % (lab, knd, len(sub), real_pct, pl.mean(),
                   real_pct - pl.mean(), float((pl >= real_pct).mean())))
            out["%s_%s" % (lab, knd)] = dict(
                n=int(len(sub)), real=real_pct, floor=float(pl.mean()),
                excess=real_pct - float(pl.mean()),
                p=float((pl >= real_pct).mean()))

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "34_E7inf_dark.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "34_E7inf_dark.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/34_E7inf_dark.{txt,json}" % RESULTS)
    log("DARK_DONE")


if __name__ == "__main__":
    main()
