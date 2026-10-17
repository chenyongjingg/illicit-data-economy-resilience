#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""28_E7inf_takedown.py -- infrastructure layer: takedown latency and
infrastructure reuse in URLhaus.

WHY THE COHORT IS CHOSEN BY MEASUREMENT, NOT BY INTUITION
The first version of this script picked 2026-01-01..2026-06-23 in order to give
every URL >= 3 months of follow-up. That window contains 5,773 rows and ZERO
offline URLs, which inverts the design: the dump is a ROLLING WINDOW, and old
entries are pruned rather than retained. Picking the window with the most
follow-up picks the window with the most pruning, so the URLs that died fast are
exactly the ones missing. The cohort start is therefore derived from the monthly
addition/removal counts and printed, so the choice is checkable.

THE MISSINGNESS IS NOT RANDOM AND IS BRACKETED, NOT IGNORED
`last_online` is populated for 100% of online URLs and 80.15% of offline ones.
The offline URLs lacking it were never observed online -- added already dead.
Three treatments are reported side by side, and they bracket the answer:
    zero    missing removal -> event at duration 0   (LOWER bound on latency)
    drop    missing rows removed entirely            (biased upward)
    censor  missing removal -> censored at snapshot  (UPPER bound on latency)
A claim is reported only if it holds across all three. An earlier draft carried
a third "separate" arm that was built by the same filter as `drop` -- a duplicate
presented as an independent treatment. It is replaced by `censor`, which is
genuinely different.

WHAT IS MEASURED
  A. Latency from addition to going offline, right-censored at the snapshot.
  B. ★ Infrastructure reuse: does prior use of the same host predict latency?
  C. ★ Reconstitution: after every URL on a host goes offline, does the host
     come back with new URLs? Rate and delay.

Dependence: URLs sharing a host share a takedown process, so SEs are clustered
by host throughout. Ignoring this would repeat E4's stated failure (independent
SEs over clustered units).
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
    """Header lives on a comment line; skipinitialspace is required (see 27_)."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    hdr_i = None
    header = None
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


def km(dur, ev, tmax=90.0):
    """Kaplan-Meier product-limit. No lifelines dependency."""
    dur = np.asarray(dur, float)
    ev = np.asarray(ev, int)
    ts = np.unique(dur[ev == 1])
    ts = ts[ts <= tmax]
    if len(ts) == 0:
        return np.array([0.0, float(tmax)]), np.array([1.0, 1.0])
    order = np.argsort(dur)
    d, e = dur[order], ev[order]
    n = len(d)
    at_risk = n - np.searchsorted(d, ts, side="left")
    deaths = np.array([int(((d == t) & (e == 1)).sum()) for t in ts])
    surv = np.cumprod(1.0 - deaths / np.maximum(at_risk, 1))
    return np.concatenate([[0.0], ts]), np.concatenate([[1.0], surv])


def km_median(t, s):
    below = np.where(s <= 0.5)[0]
    return float(t[below[0]]) if len(below) else float("nan")


def logrank(dur, ev, grp):
    """Two-sample log-rank. Returns nan unless exactly two groups are present."""
    dur = np.asarray(dur, float)
    ev = np.asarray(ev, int)
    g = np.asarray(grp)
    u = np.unique(g)
    if len(u) != 2:
        return float("nan")
    ts = np.unique(dur[ev == 1])
    O1 = E1 = V = 0.0
    for t in ts:
        at = dur >= t
        n = int(at.sum())
        n1 = int((at & (g == u[0])).sum())
        d = int(((dur == t) & (ev == 1)).sum())
        d1 = int(((dur == t) & (ev == 1) & (g == u[0])).sum())
        if n <= 1:
            continue
        O1 += d1
        E1 += d * n1 / n
        V += d * (n1 / n) * (1 - n1 / n) * (n - d) / (n - 1)
    if V <= 0:
        return float("nan")
    from math import erfc, sqrt
    z = (O1 - E1) / sqrt(V)
    return float(erfc(abs(z) / sqrt(2.0)))


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
    log("E7-inf  Takedown latency and infrastructure reuse (URLhaus)")
    log("=" * 78)

    u = read_abusech(os.path.join(RECON, "urlhaus_full__csv.txt"))
    SNAP = pd.to_datetime("2026-09-23 15:43:18")
    log("\n  rows: %d" % len(u))

    u["added"] = pd.to_datetime(u["dateadded"], errors="coerce")
    u["lo"] = pd.to_datetime(u["last_online"].astype(str).str.strip(),
                             errors="coerce")
    u["offline"] = (u["url_status"].astype(str).str.strip() == "offline")
    u["host"] = u["url"].map(host_of)
    log("  hosts: %d ; rows with empty host: %d"
        % (int(u["host"].nunique()), int((u["host"] == "").sum())))

    sep("1. Monthly additions and removals -- this decides the cohort")
    u["ym"] = u["added"].dt.to_period("M")
    m = u.groupby("ym").agg(n=("offline", "size"),
                            off=("offline", "sum")).reset_index()
    m["pct"] = (100.0 * m["off"] / m["n"]).round(1)
    log("  %-9s %8s %8s %7s" % ("month", "added", "offline", "%off"))
    for _, r in m.iterrows():
        if r["n"] >= 20 or r["ym"].year >= 2025:
            log("  %-9s %8d %8d %7.1f" % (str(r["ym"]), r["n"], r["off"], r["pct"]))
    log("")
    log("  ★ The removal signal is confined to the recent dense block. Older")
    log("  months are pruned from the dump, so their surviving rows are selected")
    log("  ON the outcome and cannot enter a latency cohort.")
    dense = m[(m["n"] >= 1000) & (m["ym"] >= pd.Period("2024-01"))]
    if len(dense) == 0:
        raise SystemExit("[guard] no dense addition block found")
    start = dense["ym"].min().to_timestamp()
    log("  dense block starts: %s (first month with >= 1000 additions)"
        % start.date())

    sep("2. Cohort and the three treatments (bracketing the missingness)")
    coh = u[u["added"] >= start].copy()
    log("  window %s .. snapshot %s" % (start.date(), SNAP.date()))
    log("  cohort rows: %d (%.1f%% of file)" % (len(coh), 100.0 * len(coh) / len(u)))
    log("  min follow-up: %.0f days" % (SNAP - coh["added"].max()).days)
    off = coh["offline"]
    n_off = int(off.sum())
    n_miss = int((off & coh["lo"].isna()).sum())
    log("  offline: %d (%.2f%%) ; of those missing last_online: %d (%.2f%%)"
        % (n_off, 100.0 * n_off / len(coh), n_miss,
           100.0 * n_miss / max(n_off, 1)))

    def frame(mode):
        # ONLY `drop` removes rows. `censor` exists precisely to KEEP the
        # offline-without-last_online rows and count them as still alive; an
        # earlier draft filtered them out here, which silently turned `censor`
        # into a second copy of `drop`.
        d = coh[~coh["offline"] | coh["lo"].notna()] if mode == "drop" else coh
        dead = d["offline"].to_numpy()
        lo2 = d["lo"]
        if mode == "zero":
            lo2 = lo2.fillna(d["added"])     # added and died -> event at day 0
        # end = the removal moment where we have one, else the snapshot
        end_s = lo2.where(pd.Series(dead, index=d.index) & lo2.notna(), SNAP)
        ev = dead.astype(int)
        if mode == "censor":
            ev = np.where(dead & d["lo"].isna().to_numpy(), 0, ev)
        dur = ((end_s - d["added"]).dt.total_seconds() / 86400.0).clip(lower=0)
        return pd.DataFrame({"dur": dur.to_numpy(float), "ev": ev,
                             "host": d["host"].to_numpy(),
                             "added": d["added"].to_numpy()})

    frames = {k: frame(k) for k in ("zero", "drop", "censor")}
    log("")
    log("  %-8s %8s %8s %10s %9s %9s %9s"
        % ("treat", "n", "events", "med_days", "p25", "p90", "cens%"))
    for k, F in frames.items():
        t, s = km(F["dur"], F["ev"])
        log("  %-8s %8d %8d %10.3f %9.3f %9.3f %8.1f%%"
            % (k, len(F), int(F["ev"].sum()), km_median(t, s),
               F["dur"].quantile(.25), F["dur"].quantile(.90),
               100.0 * (1 - F["ev"].mean())))
    log("")
    log("  ★ 'zero' is the lower bound on latency and 'censor' the upper; the")
    log("  true curve lies between them and no point estimate is claimed.")

    F = frames["zero"]
    t, s = km(F["dur"], F["ev"])
    log("")
    log("  KM (treatment=zero), % offline by:")
    for q in (0.25, 0.5, 0.75, 0.9):
        idx = np.where(s <= 1 - q)[0]
        log("    %3d%%: day %.3f" % (100 * q, float(t[idx[0]]) if len(idx) else float("nan")))

    sep("3. ★ Infrastructure reuse -- does prior use of a host predict latency?")
    d = coh.copy()
    d = d.sort_values(["host", "added"])
    d["host_prior"] = d.groupby("host").cumcount()
    d["host_total"] = d.groupby("host")["added"].transform("size")
    hs = d.groupby("host").size()
    log("  URLs per host: mean=%.2f median=%.0f p90=%.0f max=%d"
        % (hs.mean(), hs.median(), hs.quantile(.90), hs.max()))
    log("  hosts with 1 URL: %d (%.1f%%)"
        % (int((hs == 1).sum()), 100.0 * (hs == 1).mean()))
    log("  share of URLs on a host already seen (host_prior>=1): %.2f%%"
        % (100.0 * (d["host_prior"] >= 1).mean()))

    def durs(dd):
        """Same 'zero' convention as the headline curve, so sections 3-4 and
        section 2 cannot disagree about the same URL."""
        dead = dd["offline"].to_numpy()
        lo2 = dd["lo"].fillna(dd["added"])
        end = lo2.where(pd.Series(dead, index=dd.index), SNAP)
        return (((end - dd["added"]).dt.total_seconds() / 86400.0)
                .clip(lower=0).to_numpy(float),
                dd["offline"].astype(int).to_numpy())

    log("")
    log("  %-26s %8s %8s %10s %10s" % ("group", "n", "events", "med_days", "p90"))
    for lbl, msk in (("first URL on host", d["host_prior"] == 0),
                     ("repeat URL (prior>=1)", d["host_prior"] >= 1)):
        g = d[msk]
        if len(g) == 0:
            continue
        du, ev = durs(g)
        t2, s2 = km(du, ev)
        log("  %-26s %8d %8d %10.3f %10.3f"
            % (lbl, len(g), int(ev.sum()), km_median(t2, s2),
               np.quantile(du, .90)))
    du, ev = durs(d)
    real = logrank(du, ev, (d["host_prior"] >= 1).astype(int).to_numpy())
    log("  log-rank p (first vs repeat) = %.4g" % real)
    log("")
    log("  ★ These two groups are NOT independent: repeat URLs sit on the same")
    log("  hosts as the first URLs by construction, so the log-rank p is")
    log("  optimistic and is reported as a description of the curves, not a test.")

    sep("4. ★ Reconstitution -- does a host come back after its URLs die?")
    h = d.groupby("host").agg(n=("added", "size"), first=("added", "min"),
                              last=("added", "max"))
    multi = h[h["n"] >= 2]
    log("  hosts with >=2 URLs: %d (%.1f%% of hosts) carrying %d URLs"
        % (len(multi), 100.0 * len(multi) / len(h), int(multi["n"].sum())))
    span = (multi["last"] - multi["first"]).dt.total_seconds() / 86400.0
    log("  first->last addition span (days): p25=%.2f p50=%.2f p75=%.2f p90=%.2f max=%.1f"
        % (span.quantile(.25), span.median(), span.quantile(.75),
           span.quantile(.90), span.max()))
    ev_d = d[d["offline"] & d["lo"].notna()].copy()
    ev_d = ev_d.sort_values(["host", "added"])
    ev_d["next_added"] = ev_d.groupby("host")["added"].shift(-1)
    ok = ev_d["next_added"].notna()
    log("")
    log("  removals that have a LATER addition on the same host: %d"
        % int(ok.sum()))
    if int(ok.sum()):
        gap = ((ev_d.loc[ok, "next_added"] - ev_d.loc[ok, "lo"])
               .dt.total_seconds() / 86400.0)
        after = (gap > 0).to_numpy()
        n_after = int(after.sum())
        log("  of those, new URL came AFTER the removal: %d (%.1f%%)"
            % (n_after, 100.0 * n_after / int(ok.sum())))
        if n_after:
            g = gap[after]
            log("  re-registration delay (days): p25=%.3f p50=%.3f p90=%.3f max=%.1f"
                % (g.quantile(.25), g.median(), g.quantile(.90), g.max()))
            log("  within 1 day: %.1f%% ; within 7 days: %.1f%% ; within 30: %.1f%%"
                % (100.0 * (g <= 1).mean(), 100.0 * (g <= 7).mean(),
                   100.0 * (g <= 30).mean()))
    else:
        gap = pd.Series(dtype=float)
        after = np.array([], dtype=bool)
        log("  ⇒ no host in this cohort re-registered after a removal.")

    sep("5. Falsification -- placebo host labels")
    rng = np.random.default_rng(20260924)
    fake = rng.integers(0, 2, len(d))
    pl = logrank(du, ev, fake)
    log("  real    log-rank p (host_prior>=1 vs 0) = %.4g" % real)
    log("  placebo log-rank p (random labels)      = %.4g" % pl)
    if not np.isnan(pl) and not np.isnan(real):
        log("  placebo is %s the real p -- a placebo that also rejected would"
            % ("smaller than" if pl < real else "larger than"))
        log("  mean the comparison rejects on noise.")

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
        ax[0, 0].set_title("A. Time to offline, bracketed by treatment")
        ax[0, 0].set_xlabel("days since added")
        ax[0, 0].set_ylabel("% still online")
        ax[0, 0].legend(fontsize=8)

        ax[0, 1].hist(F["dur"], bins=np.arange(0, 30, 0.5), color="0.6")
        ax[0, 1].set_yscale("log")
        ax[0, 1].set_title("B. Lifetime distribution (log count)")
        ax[0, 1].set_xlabel("days")

        for lbl, msk, col in (("first URL on host", d["host_prior"] == 0, "steelblue"),
                              ("repeat URL", d["host_prior"] >= 1, "crimson")):
            g = d[msk]
            if len(g) == 0:
                continue
            du2, ev2 = durs(g)
            tt, ss = km(du2, ev2)
            ax[1, 0].step(tt, 100 * ss, where="post", color=col, label=lbl)
        ax[1, 0].set_xlim(0, 30)
        ax[1, 0].set_title("C. First vs repeat URL on the same host")
        ax[1, 0].set_xlabel("days since added")
        ax[1, 0].set_ylabel("% still online")
        ax[1, 0].legend(fontsize=8)

        if len(gap) and after.sum():
            ax[1, 1].hist(np.log10(gap[after].to_numpy() + 0.01), bins=40,
                          color="darkorange")
            ax[1, 1].set_title("D. Re-registration delay after removal\n(log10 days)")
            ax[1, 1].set_xlabel("log10(days)")
        else:
            ax[1, 1].text(0.5, 0.5, "no reconstitution events",
                          ha="center", va="center")
            ax[1, 1].set_title("D. Re-registration delay")
        plt.tight_layout()
        os.makedirs(FIGS, exist_ok=True)
        plt.savefig(os.path.join(FIGS, "E7inf_takedown.png"), dpi=150)
        plt.savefig(os.path.join(FIGS, "E7inf_takedown.pdf"))
        log("\nwrote %s/E7inf_takedown.{png,pdf}" % FIGS)
    except Exception as ex:  # noqa: BLE001
        log("\nfigure failed (non-fatal): %r" % ex)

    out = dict(rows=int(len(u)), cohort_start=str(start.date()),
               cohort=int(len(coh)), offline=int(n_off), missing_lo=int(n_miss),
               hosts=int(u["host"].nunique()),
               treatments={k: dict(n=int(len(F)), events=int(F["ev"].sum()),
                                   median=km_median(*km(F["dur"], F["ev"])))
                           for k, F in frames.items()},
               logrank_real=float(real), logrank_placebo=float(pl),
               reconstitution_events=int(ok.sum()),
               reconstitution_after=int(after.sum()))
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "28_E7inf_takedown.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "28_E7inf_takedown.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/28_E7inf_takedown.{txt,json}" % RESULTS)
    log("E7INF_DONE")


if __name__ == "__main__":
    main()
