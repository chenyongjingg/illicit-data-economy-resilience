#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""30_E7inf_v2.py -- infrastructure layer, corrected cohort and corrected tests.

WHAT 28_ GOT WRONG, AND WHY IT MATTERED
28_ chose its cohort by "everything from the first dense addition month"
(2025-03), giving 56,708 rows. 29_ then measured the thing 28_ had assumed:

    pre-2026-06 : 8,703 rows, offline = 0
    2026-06+    : 49,607 rows, offline = 42,272

and every one of those 8,703 rows has `last_online` populated -- 100% of them,
all within 0.4 days of the snapshot (median 0.18 d), i.e. one crawl cycle.

So `last_online` carries TWO meanings in one column:
    row is `online`   -> last_online is the CRAWL STAMP (~the snapshot)
    row is `offline`  -> last_online is when it was last seen ALIVE (removal)
and the reason no pre-2026-06 row is ever `offline` is that URLhaus PRUNES
entries that have stopped resolving, so an old row survives only by still
resolving. That is selection on the outcome. Including those rows put ~8,700
perpetually-censored, 7-year-long observations into 28_'s KM curve, which is why
its 90th percentile came back `nan`.

DESIGN DEFECTS OF MINE CORRECTED HERE
  D1 (cohort)     rows added before the pruning boundary must leave the risk set
  D2 (§4 rate)    28_ reported "19.0% came after the removal" among removals that
                  HAVE a later addition -- selecting on the event. The correct
                  denominator is ALL removals on the host, with the window
                  right-censored at the snapshot so removals near the snapshot
                  cannot be counted as non-reconstituting.
  D3 (§3 bias)    28_ compared the first URL on a host to repeat URLs on the same
                  host. A host can only produce a repeat URL if it SURVIVED to be
                  reused, so the contrast is contaminated by immortal-time /
                  selection-on-survival. Replaced by a WITHIN-HOST paired design
                  (the host is its own control, so selection into multi-URL hosts
                  cancels) on a binary outcome (offline within 7 days), which
                  restricts to URLs with full follow-up and so has no censoring
                  problem either.

THE CORRECTED PICTURE
  2026 additions: 50,527 = 42,272 offline (83.7%) + 8,255 online (16.3%)
  of the offline: 33,881 carry a removal time; 8,391 never seen alive (NaT)
"""
from __future__ import annotations

import io
import json
import os
from urllib.parse import urlparse

import numpy as np
import pandas as pd

RECON = "/root/cis/data/_recon/abusech"
RESULTS = "/root/cis/results"
FIGS = os.path.join(RESULTS, "figs")
SNAP = pd.to_datetime("2026-09-23 15:43:18")
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
        raise SystemExit("no header found in %s" % path)
    cols = [c.strip().strip('"') for c in header.split(",")]
    return pd.read_csv(io.StringIO("".join(lines[hdr_i + 1:])), header=None,
                       names=cols, low_memory=False, skipinitialspace=True)


def km(dur, ev, tmax=60.0):
    dur = np.asarray(dur, float)
    ev = np.asarray(ev, int)
    ts = np.unique(dur[ev == 1])
    ts = ts[ts <= tmax]
    if len(ts) == 0:
        return np.array([0.0, float(tmax)]), np.array([1.0, 1.0])
    order = np.argsort(dur)
    d, e = dur[order], ev[order]
    at_risk = len(d) - np.searchsorted(d, ts, side="left")
    deaths = np.array([int(((d == t) & (e == 1)).sum()) for t in ts])
    return (np.concatenate([[0.0], ts]),
            np.concatenate([[1.0], np.cumprod(1.0 - deaths / np.maximum(at_risk, 1))]))


def km_median(t, s):
    b = np.where(s <= 0.5)[0]
    return float(t[b[0]]) if len(b) else float("nan")


def km_q(t, s, q):
    b = np.where(s <= 1 - q)[0]
    return float(t[b[0]]) if len(b) else float("nan")


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


def binom_two_sided(k, n, p=0.5):
    """Exact two-sided binomial p, no scipy."""
    if n == 0:
        return float("nan")
    from math import comb
    pmf = [comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(n + 1)]
    obs = pmf[k]
    return float(min(1.0, sum(v for v in pmf if v <= obs + 1e-12)))


def main():
    log("=" * 78)
    log("E7-inf v2  Takedown latency and reconstitution (corrected cohort)")
    log("=" * 78)

    u = read_abusech(os.path.join(RECON, "urlhaus_full__csv.txt"))
    u["added"] = pd.to_datetime(u["dateadded"], errors="coerce")
    u["lo"] = pd.to_datetime(u["last_online"].astype(str).str.strip(),
                             errors="coerce")
    u["offline"] = (u["url_status"].astype(str).str.strip() == "offline")
    u["host"] = u["url"].map(host_of)
    log("\n  rows: %d ; distinct hosts: %d"
        % (len(u), int(u["host"].nunique())))

    sep("1. Locating the pruning boundary to the day (no filter, every day)")
    d = u[u["added"] >= pd.to_datetime("2026-06-10")].copy()
    d["day"] = d["added"].dt.normalize()
    g = d.groupby("day").agg(n=("offline", "size"), off=("offline", "sum"))
    g["pct"] = (100.0 * g["off"] / g["n"]).round(1)
    log("  %-12s %7s %7s %8s" % ("day", "n", "off", "%off"))
    for day, r in g.iterrows():
        log("  %-12s %7d %7d %7.1f%%"
            % (pd.Timestamp(day).date(), r["n"], r["off"], r["pct"]))
    log("")
    # The boundary is not chosen by hand. It is the first day after which no
    # day with a meaningful sample ever again shows a zero removal rate.
    big = g[g["n"] >= 50]
    CUT = None
    for day in big.index:
        tail = big.loc[day:]
        if tail["pct"].min() > 0.0:
            CUT = pd.Timestamp(day)
            break
    if CUT is None:
        raise SystemExit("[guard] could not locate the pruning boundary")
    log("  ★ Detected boundary: %s -- the first day after which every day with")
    log("  n>=50 has a non-zero removal rate.")
    log("  Before it removal is NEVER recorded, so those rows survive by still")
    log("  resolving. That is selection on the outcome, and it is a property of")
    log("  the DUMP, not of the URLs.")

    sep("2. Corrected cohort")
    CUT = CUT
    coh = u[u["added"] >= CUT].copy()
    log("  cohort = added >= %s" % CUT.date())
    log("  rows: %d (%.1f%% of file)" % (len(coh), 100.0 * len(coh) / len(u)))
    log("  offline: %d (%.2f%%) ; online (censored): %d"
        % (int(coh["offline"].sum()), 100.0 * coh["offline"].mean(),
           int((~coh["offline"]).sum())))
    log("  offline with a removal time: %d ; without: %d"
        % (int((coh["offline"] & coh["lo"].notna()).sum()),
           int((coh["offline"] & coh["lo"].isna()).sum())))
    log("  follow-up: %.0f days from cohort start to snapshot"
        % (SNAP - CUT).days)

    def frame(mode):
        dd = coh[~coh["offline"] | coh["lo"].notna()] if mode == "drop" else coh
        dead = dd["offline"].to_numpy()
        lo2 = dd["lo"]
        if mode == "zero":
            lo2 = lo2.fillna(dd["added"])
        end = lo2.where(pd.Series(dead, index=dd.index) & lo2.notna(), SNAP)
        ev = dead.astype(int)
        if mode == "censor":
            ev = np.where(dead & dd["lo"].isna().to_numpy(), 0, ev)
        dur = ((end - dd["added"]).dt.total_seconds() / 86400.0).clip(lower=0)
        return pd.DataFrame({"dur": dur.to_numpy(float), "ev": ev,
                             "host": dd["host"].to_numpy(),
                             "added": dd["added"].to_numpy()})

    frames = {k: frame(k) for k in ("zero", "drop", "censor")}
    log("")
    log("  %-8s %8s %8s %9s %9s %9s %8s"
        % ("treat", "n", "events", "med", "q25", "q75", "cens%"))
    for k, F in frames.items():
        t, s = km(F["dur"], F["ev"])
        log("  %-8s %8d %8d %9.3f %9.3f %9.3f %7.1f%%"
            % (k, len(F), int(F["ev"].sum()), km_median(t, s),
               km_q(t, s, .25), km_q(t, s, .75), 100.0 * (1 - F["ev"].mean())))
    log("")
    log("  ★ The three treatments bracket the answer; no point estimate claimed.")

    F = frames["zero"]
    tz, sz = km(F["dur"], F["ev"])
    log("")
    log("  KM (zero), %% offline by day:")
    log("    " + "  ".join("%d%%:%.2f" % (100 * q, km_q(tz, sz, q))
                           for q in (.1, .25, .5, .75, .9)))

    sep("3. ★ Within-host paired test (host is its own control)")
    log("  28_ compared first-vs-repeat URLs across hosts. A host can only")
    log("  produce a repeat URL if it SURVIVED to be reused, so that contrast")
    log("  was contaminated. Here the comparison is WITHIN hosts that have >=2")
    log("  URLs, so selection into the multi-URL set cancels.")
    coh2 = coh.sort_values(["host", "added"]).copy()
    coh2["rank"] = coh2.groupby("host").cumcount()
    coh2["nsib"] = coh2.groupby("host")["added"].transform("size")
    mh = coh2[coh2["nsib"] >= 2].copy()
    log("  hosts with >=2 URLs: %d ; URLs in them: %d"
        % (int(mh["host"].nunique()), len(mh)))
    log("  URLs per host: median=%.0f p90=%.0f max=%d"
        % (mh.groupby("host").size().median(),
           mh.groupby("host").size().quantile(.90),
           int(mh.groupby("host").size().max())))

    # binary outcome with FULL follow-up: offline within 7 days of addition
    H = 7.0
    ok = mh[(SNAP - mh["added"]).dt.total_seconds() / 86400.0 >= H].copy()
    log("  URLs with >= %.0f days follow-up: %d (%.1f%% of the multi-host set)"
        % (H, len(ok), 100.0 * len(ok) / len(mh)))
    ok["died7"] = ((ok["offline"]) & (ok["lo"].notna())
                   & (((ok["lo"] - ok["added"]).dt.total_seconds() / 86400.0)
                      <= H))
    first = ok[ok["rank"] == 0]
    later = ok[ok["rank"] >= 1].groupby("host")["died7"].mean()
    both = first.set_index("host")["died7"].to_frame("f").join(later.to_frame("l"))
    both = both.dropna()
    log("")
    log("  hosts usable for the paired test: %d" % len(both))
    log("  died-within-7d, first URL : %.4f (n=%d)"
        % (both["f"].mean(), len(both)))
    log("  died-within-7d, later URLs: %.4f" % both["l"].mean())
    diff = both["l"].astype(float) - both["f"].astype(float)
    nz = diff[diff != 0]
    log("  hosts where later < first: %d ; later > first: %d ; tied: %d"
        % (int((diff < 0).sum()), int((diff > 0).sum()), int((diff == 0).sum())))
    p = binom_two_sided(int((diff > 0).sum()), len(nz))
    log("  sign test p (two-sided) = %.4g   [n discordant = %d]" % (p, len(nz)))
    log("  mean within-host difference (later - first) = %+.4f" % diff.mean())
    log("")
    log("  ★ A NEGATIVE difference means later URLs on the same host die FASTER")
    log("  than the host's first URL; positive means reused hosts are stickier.")

    sep("4. ★ Reconstitution rate, with the correct denominator (D2 fixed)")
    log("  Denominator = EVERY removal on a host with >=2 URLs, not only those")
    log("  followed by an addition. For a window of W days, only removals with")
    log("  at least W days of follow-up can be counted, or a removal near the")
    log("  snapshot would be scored as a non-reconstitution it never had time")
    log("  to contradict.")
    rm = coh[(coh["offline"]) & coh["lo"].notna()].copy()
    hs = coh.groupby("host").size()
    rm = rm[rm["host"].isin(hs[hs >= 2].index)]
    add_by_host = {h: np.sort(g["added"].to_numpy())
                   for h, g in coh.groupby("host")}
    log("  candidate removals (host has >=2 URLs): %d" % len(rm))
    log("")
    log("  %4s %9s %11s %12s %12s" % ("W", "n_used", "recon", "rate", "median_gap"))
    recon_tbl = []
    for W in (1, 3, 7, 30):
        sub = rm[(SNAP - rm["lo"]).dt.total_seconds() / 86400.0 >= W]
        if len(sub) == 0:
            continue
        hit, gaps = 0, []
        for lo_t, h in zip(sub["lo"].to_numpy(), sub["host"].to_numpy()):
            arr = add_by_host[h]
            j = np.searchsorted(arr, lo_t, side="right")
            if j < len(arr) and (arr[j] - lo_t) / np.timedelta64(1, "D") <= W:
                hit += 1
                gaps.append((arr[j] - lo_t) / np.timedelta64(1, "D"))
        rate = 100.0 * hit / len(sub)
        gmed = float(np.median(gaps)) if gaps else float("nan")
        recon_tbl.append(dict(W=W, n=int(len(sub)), hits=int(hit), rate=rate))
        log("  %4d %9d %11d %11.2f%% %12.3f"
            % (W, len(sub), hit, rate, gmed))
    log("")
    log("  ★ This is the displacement/resilience measure: a removal is followed")
    log("  by a new URL on the same host within W days at the rate above.")
    log("  It has no immortal-time problem because every host in the")
    log("  denominator has an OBSERVED removal.")

    sep("5. Falsification -- placebo removal times")
    rng = np.random.default_rng(20260924)
    W = 7
    sub = rm[(SNAP - rm["lo"]).dt.total_seconds() / 86400.0 >= W]
    real_hit = 0
    for lo_t, h in zip(sub["lo"].to_numpy(), sub["host"].to_numpy()):
        arr = add_by_host[h]
        j = np.searchsorted(arr, lo_t, side="right")
        if j < len(arr) and (arr[j] - lo_t) / np.timedelta64(1, "D") <= W:
            real_hit += 1
    real_rate = 100.0 * real_hit / max(len(sub), 1)
    # placebo: shuffle the removal times across hosts, keeping the window
    pl_rates = []
    lo_vals = sub["lo"].to_numpy()
    for _ in range(200):
        perm = rng.permutation(lo_vals)
        hit = 0
        for lo_t, h in zip(perm, sub["host"].to_numpy()):
            arr = add_by_host[h]
            j = np.searchsorted(arr, lo_t, side="right")
            if j < len(arr) and (arr[j] - lo_t) / np.timedelta64(1, "D") <= W:
                hit += 1
        pl_rates.append(100.0 * hit / max(len(sub), 1))
    pl = np.array(pl_rates)
    log("  real   reconstitution rate (W=7d) = %.2f%%" % real_rate)
    log("  placebo (removal times shuffled)  = %.2f%% (sd %.2f), p = %.4f"
        % (pl.mean(), pl.std(), float((pl >= real_rate).mean())))
    log("  ★ The placebo keeps the same hosts, the same additions and the same")
    log("  number of removals, and only breaks the pairing -- so a real rate")
    log("  far above the placebo is evidence the pairing carries information.")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 2, figsize=(13, 9))
        for k, col in (("zero", "steelblue"), ("drop", "crimson"),
                       ("censor", "darkgreen")):
            tt, ss = km(frames[k]["dur"], frames[k]["ev"])
            ax[0, 0].step(tt, 100 * ss, where="post", color=col, label=k)
        ax[0, 0].set_xlim(0, 30)
        ax[0, 0].set_title("A. Time to offline (cohort = additions from 2026-06)")
        ax[0, 0].set_xlabel("days since added")
        ax[0, 0].set_ylabel("% still online")
        ax[0, 0].legend(fontsize=8)

        ax[0, 1].hist(F["dur"].to_numpy(), bins=np.arange(0, 30, .5), color="0.6")
        ax[0, 1].set_yscale("log")
        ax[0, 1].set_title("B. Lifetime distribution (log count)")
        ax[0, 1].set_xlabel("days")

        ws = [r["W"] for r in recon_tbl]
        rs = [r["rate"] for r in recon_tbl]
        ax[1, 0].bar([str(w) for w in ws], rs, color="purple")
        ax[1, 0].set_title("C. Reconstitution rate by window\n(new URL on the "
                           "same host after a removal)")
        ax[1, 0].set_xlabel("window W (days)")
        ax[1, 0].set_ylabel("% of removals followed")

        ax[1, 1].hist(pl, bins=30, color="0.7")
        ax[1, 1].axvline(real_rate, color="crimson", lw=2, label="observed")
        ax[1, 1].set_title("D. Placebo null (W=7d)")
        ax[1, 1].set_xlabel("reconstitution rate (%)")
        ax[1, 1].legend(fontsize=8)
        plt.tight_layout()
        os.makedirs(FIGS, exist_ok=True)
        plt.savefig(os.path.join(FIGS, "E7inf_v2.png"), dpi=150)
        plt.savefig(os.path.join(FIGS, "E7inf_v2.pdf"))
        log("\nwrote %s/E7inf_v2.{png,pdf}" % FIGS)
    except Exception as ex:  # noqa: BLE001
        log("\nfigure failed (non-fatal): %r" % ex)

    out = dict(cohort=int(len(coh)), cohort_start=str(CUT.date()),
               offline=int(coh["offline"].sum()),
               treatments={k: dict(n=int(len(F_)), events=int(F_["ev"].sum()),
                                   median=km_median(*km(F_["dur"], F_["ev"])))
                           for k, F_ in frames.items()},
               within_host=dict(n_hosts=int(len(both)),
                                first_rate=float(both["f"].mean()),
                                later_rate=float(both["l"].mean()),
                                mean_diff=float(diff.mean()),
                                sign_p=float(p), n_discordant=int(len(nz))),
               reconstitution=recon_tbl,
               placebo_rate=float(pl.mean()),
               real_rate_7d=float(real_rate))
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "30_E7inf_v2.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "30_E7inf_v2.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/30_E7inf_v2.{txt,json}" % RESULTS)
    log("E7INF2_DONE")


if __name__ == "__main__":
    main()
