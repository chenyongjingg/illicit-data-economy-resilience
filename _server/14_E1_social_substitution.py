#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""14_E1_social_substitution.py -- E1: when a market dies, where does its trade go?

The question
------------
`12_` and `13_` showed that the five dated Kilos markets move together in a very
specific way. Cryptonia runs at ~500 reviews/day and stops dead on 2019-11-17;
Cannazon runs at ~300/day and collapses on 2019-11-18; Empire peaks 2019-11-08
and then falls away. Over the same weeks **Apollon rises from 4,461 reviews in
October to 23,511 in December**, and CannaHome rises too.

That is the pattern the whole project is about: a market-level shock that does
not reduce aggregate activity but redistributes it. It is also the pattern that
is easiest to fake, because a scraper that quietly re-weighted its coverage would
produce the identical time series without one seller ever moving.

What is identified here, and what is not
----------------------------------------
The design is a **seller-level difference-in-differences on a surviving
market**. Apollon is chosen because it (i) survives the shock and (ii) is one of
only two markets with a real clock (`13_`: 780 distinct seconds-of-day), so its
weekly series is not an artefact of date rounding.

  unit      seller x week, outcome = reviews written in Apollon
  treated   sellers with >=1 review in Cryptonia or Cannazon before 2019-11-18
  control   sellers active in Apollon before the event, never in Cryptonia/Cannazon
  model     two-way fixed effects (seller + week), cluster-robust by seller

Why the market-wide confound cannot produce this. A change in how Kilos scraped
Apollon would move every Apollon seller at once, and is absorbed by the **week
fixed effects**. The DiD coefficient asks only whether *Cryptonia-exposed* sellers
rose more than *unexposed* sellers in the same weeks. Scraper re-weighting cannot
answer that; only reallocation of sellers can.

Two limits, stated because they cut in opposite directions:
  * treatment is assigned by **handle match**, and `11_` established there is no
    key tying a handle to a person. Sellers who changed handle between markets are
    misfiled as controls, which **attenuates** the estimate toward zero. So a
    positive finding survives this; a null does not distinguish "nobody moved"
    from "people moved and changed their name".
  * `13_` showed Cannazon/Cryptonia/CannaHome carry **dates, not times**, so the
    event day is +/- 1 day for those markets. Everything here is at weekly
    resolution precisely to make that irrelevant.

The placebo is the part that matters: the same DiD run at a date when nothing
happened. If the placebo also shows an "effect", the design is measuring trend,
not shock.
"""
from __future__ import annotations

import json
import os
import sys
import traceback

import numpy as np
import pandas as pd

WORK = "/root/cis/work"
RESULTS = "/root/cis/results"
FIGDIR = os.path.join(RESULTS, "figs")

MARKETS = ["Empire", "Cannazon", "Apollon", "Cryptonia", "CannaHome"]
DEAD = ["Cryptonia", "Cannazon"]           # collapse on 2019-11-17/18
EVENT = pd.Timestamp("2019-11-18")
PRE0 = pd.Timestamp("2019-06-03")          # ~24 weeks before
POST1 = pd.Timestamp("2020-01-12")

_L: list[str] = []
R: dict = {}


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _L.append(s)


def sep(t):
    log("")
    log("=" * 78)
    log(t)
    log("=" * 78)


# --------------------------------------------------------------- estimation
def twoway_did(panel, ycol="y", treat="treat", post="post", cl="seller"):
    """Two-way FE DiD via alternating projections + cluster-robust SEs.

    Written out rather than delegated so the variance model is auditable: the
    standard errors are clustered by seller, and the within-transform removes
    both seller and week means. Nothing here should be trusted more than the
    placebo below, which is the real check.
    """
    d = panel.dropna(subset=[ycol]).copy()
    y = d[ycol].to_numpy(float)
    n = len(y)

    sid = pd.factorize(d[cl])[0]
    wid = pd.factorize(d["week"])[0]

    # alternating projections onto the orthogonal complement of both FE spaces
    yr = y - y.mean()
    for _ in range(60):
        prev = yr.copy()
        m = np.bincount(sid, yr, minlength=sid.max() + 1) / np.maximum(
            np.bincount(sid, minlength=sid.max() + 1), 1)
        yr = yr - m[sid]
        m = np.bincount(wid, yr, minlength=wid.max() + 1) / np.maximum(
            np.bincount(wid, minlength=wid.max() + 1), 1)
        yr = yr - m[wid]
        if np.max(np.abs(yr - prev)) < 1e-10:
            break

    x = (d[treat].to_numpy(float) * d[post].to_numpy(float))
    # demean the regressor the same way
    xr = x - x.mean()
    for _ in range(60):
        prev = xr.copy()
        m = np.bincount(sid, xr, minlength=sid.max() + 1) / np.maximum(
            np.bincount(sid, minlength=sid.max() + 1), 1)
        xr = xr - m[sid]
        m = np.bincount(wid, xr, minlength=wid.max() + 1) / np.maximum(
            np.bincount(wid, minlength=wid.max() + 1), 1)
        xr = xr - m[wid]
        if np.max(np.abs(xr - prev)) < 1e-10:
            break

    denom = float(xr @ xr)
    if denom <= 0:
        return None
    beta = float(xr @ yr) / denom
    resid = yr - beta * xr

    # cluster-robust (Liang-Zeger) with a finite-sample correction
    meat = 0.0
    for g in np.unique(sid):
        m = sid == g
        sg = float(xr[m] @ resid[m])
        meat += sg * sg
    G = len(np.unique(sid))
    dof = max(G / max(G - 1.0, 1.0), 1.0)
    se = float(np.sqrt(meat * dof) / denom) if denom > 0 else np.nan
    t = beta / se if se and se > 0 else np.nan
    try:
        from scipy import stats as st
        p = float(2 * st.t.sf(abs(t), G - 1))
    except Exception:  # noqa: BLE001
        p = float("nan")
    return {"beta": beta, "se": se, "t": t, "p": p, "n": n, "n_clusters": int(G)}


def build_panel(d, market, pre0=PRE0, post1=POST1, ev=EVENT):
    """Seller x week panel for `market`, with treatment from the DEAD markets."""
    m = d[d["market"] == market].copy()
    pre = d[(d["ts"] >= pre0) & (d["ts"] < ev)]
    treated = set(pre.loc[pre["market"].isin(DEAD), "vendor"])
    active_pre = set(pre.loc[pre["market"] == market, "vendor"])
    ever_dead = set(d.loc[d["market"].isin(DEAD), "vendor"])
    control = active_pre - ever_dead

    wk = m.copy()
    wk["week"] = wk["ts"].dt.to_period("W").dt.start_time
    agg = wk.groupby(["vendor", "week"]).size().rename("y").reset_index()
    agg = agg[agg["vendor"].isin(treated | control)]
    weeks = pd.date_range(pre0, post1, freq="W-MON")
    sellers = sorted(treated | control)
    full = pd.MultiIndex.from_product([sellers, weeks], names=["vendor", "week"])
    p = agg.set_index(["vendor", "week"]).reindex(full).fillna({"y": 0}).reset_index()
    p["treat"] = p["vendor"].isin(treated).astype(int)
    p["post"] = (p["week"] >= ev).astype(int)
    p = p.rename(columns={"vendor": "seller"})
    return p, treated, control


def main():
    log("=" * 78)
    log("E1 -- CROSS-MARKET SUBSTITUTION AFTER A MARKET-LEVEL SHOCK")
    log("=" * 78)
    R["event"] = str(EVENT.date())

    ks = pd.read_parquet(os.path.join(WORK, "kilos_reviews.parquet"))
    ts = pd.to_datetime(pd.to_numeric(ks["f2"], errors="coerce"), unit="s",
                        errors="coerce")
    d = ks.assign(ts=ts, market=ks["market"].astype(str).str.strip(),
                  vendor=ks["vendor"].astype(str).str.strip())
    d = d[d["market"].isin(MARKETS) & d["ts"].notna()]
    d = d[(d["vendor"] != "") & (d["vendor"].str.lower() != "nan")]

    # ---------------------------------------------------- 1. the aggregates
    sep("1. The aggregate pattern that motivates the test")
    wk = d.assign(week=d["ts"].dt.to_period("W").dt.start_time)
    piv = wk.pivot_table(index="week", columns="market", values="price",
                         aggfunc="size", fill_value=0)
    show = piv.loc[(piv.index >= "2019-09-02") & (piv.index <= "2020-01-13")]
    log(show.to_string())
    log("")
    pre = (piv.index >= PRE0) & (piv.index < EVENT)
    post = (piv.index >= EVENT) & (piv.index <= POST1)
    log("  weekly mean, pre (2019-06-03..2019-11-11) vs post (2019-11-18..):")
    for m in MARKETS:
        if m in piv:
            a, b = piv.loc[pre, m].mean(), piv.loc[post, m].mean()
            log("    %-11s %8.1f -> %8.1f  (%+.0f%%)"
                % (m, a, b, 100.0 * (b / a - 1) if a else float("nan")))
    R["aggregate"] = {m: {"pre_mean": float(piv.loc[pre, m].mean()),
                          "post_mean": float(piv.loc[post, m].mean())}
                      for m in MARKETS if m in piv}
    log("")
    log("  NOTE: Apollon/CannaHome rising while Cryptonia/Cannazon stop is")
    log("  CONSISTENT with substitution and also with the collector re-weighting")
    log("  coverage. The aggregate cannot tell them apart; only §2 can.")

    # -------------------------------------------------------- 2. the design
    sep("2. Seller-level DiD on a surviving market (Apollon)")
    survivors = ["Apollon", "Empire"]
    out = {}
    for market in survivors:
        p, treated, control = build_panel(d, market)
        log("")
        log("  --- surviving market: %s ---" % market)
        log("  panel: %d sellers x %d weeks = %d rows"
            % (p["seller"].nunique(), p["week"].nunique(), len(p)))
        log("  treated sellers (>=1 review in %s before %s): %d"
            % ("/".join(DEAD), EVENT.date(), len(treated)))
        log("  control sellers (active in %s, never in %s): %d"
            % (market, "/".join(DEAD), len(control)))
        m = twoway_did(p)
        if m is None:
            log("  !! could not estimate")
            continue
        log("  DiD beta = %+.4f  (se %.4f, t %.2f, p %.4g)  clusters=%d"
            % (m["beta"], m["se"], m["t"], m["p"], m["n_clusters"]))
        base = p.loc[(p["post"] == 0) & (p["treat"] == 1), "y"].mean()
        log("  treated pre-period mean weekly reviews in %s: %.2f" % (market, base))
        log("  -> effect as a share of the treated pre-period level: %s"
            % (("%+.0f%%" % (100.0 * m["beta"] / base)) if base else "n/a"))
        out[market] = m

    # ------------------------------------------------------- 3. pre-trends
    sep("3. Pre-trends: is the difference already there before the event?")
    p, treated, control = build_panel(d, "Apollon")
    ss = p.groupby(["seller", "treat"]).size().reset_index(name="n")
    log("  seller counts: treated=%d control=%d"
        % (int((ss["treat"] == 1).sum()), int((ss["treat"] == 0).sum())))
    trend = p.groupby(["week", "treat"])["y"].mean().unstack()
    trend.columns = ["control", "treated"] if 0 in trend.columns else trend.columns
    prew = trend.loc[trend.index < EVENT]
    log("")
    log("  mean weekly Apollon reviews per seller, by group:")
    log(prew.tail(12).round(3).to_string())
    log("")
    log("  post weeks:")
    log(trend.loc[trend.index >= EVENT].round(3).to_string())
    if "treated" in trend.columns and "control" in trend.columns:
        gp = (prew["treated"] - prew["control"])
        log("")
        log("  pre-period gap (treated - control): mean %+.3f, sd %.3f"
            % (gp.mean(), gp.std()))
        gq = (trend.loc[trend.index >= EVENT, "treated"]
              - trend.loc[trend.index >= EVENT, "control"])
        log("  post-period gap (treated - control): mean %+.3f" % gq.mean())
        log("  -> the DiD is the CHANGE in the gap; a pre-period gap that is")
        log("     already large and drifting means the FE model is doing the work,")
        log("     not the shock.")

    # --------------------------------------------------------- 4. placebo
    sep("4. Placebo: the same DiD at a date when nothing happened")
    plac = []
    for when in ["2019-08-05", "2019-09-02", "2019-10-07"]:
        ev = pd.Timestamp(when)
        pp, t2, c2 = build_panel(d, "Apollon", pre0=PRE0, post1=POST1, ev=ev)
        mm = twoway_did(pp)
        if mm:
            log("  placebo event %s: beta=%+.4f (se %.4f, p %.4g)"
                % (when, mm["beta"], mm["se"], mm["p"]))
            plac.append({"event": when, "beta": mm["beta"], "p": mm["p"]})
    log("")
    log("  A real effect should be absent at these dates. If the placebo is as")
    log("  large as the event estimate, the design is measuring trend.")
    R["placebo"] = plac

    # --------------------------------------------- 5. extensive vs intensive
    sep("5. Extensive margin: do treated sellers APPEAR in Apollon at all?")
    pp, treated, control = build_panel(d, "Apollon")
    for lbl, sub in (("treated", pp[pp["treat"] == 1]),
                     ("control", pp[pp["treat"] == 0])):
        pre = sub[sub["post"] == 0].groupby("seller")["y"].sum()
        post = sub[sub["post"] == 1].groupby("seller")["y"].sum()
        log("  %-8s sellers active in Apollon pre: %d/%d ; post: %d/%d"
            % (lbl, int((pre > 0).sum()), len(pre),
               int((post > 0).sum()), len(post)))
        new = int(((pre == 0) & (post > 0)).sum())
        gone = int(((pre > 0) & (post == 0)).sum())
        log("  %-8s entered: %d ; exited: %d" % ("", new, gone))
    log("")
    log("  The extensive margin is the migration-relevant one: a seller who had")
    log("  no Apollon presence before the shock and has one after can only have")
    log("  arrived, and that is not a change in how often anyone writes reviews.")

    # ------------------------------------------------------------ 6. figure
    sep("6. Figure")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        os.makedirs(FIGDIR, exist_ok=True)
        fig, ax = plt.subplots(1, 2, figsize=(12.5, 4.6))
        for m in MARKETS:
            if m in piv:
                ax[0].plot(piv.index, piv[m], marker="o", ms=3, label=m)
        ax[0].axvline(EVENT, ls="--", c="k", lw=1)
        ax[0].annotate("2019-11-18", (EVENT, ax[0].get_ylim()[1]), fontsize=8,
                       ha="right", va="top")
        ax[0].set_title("(a) Weekly reviews per market")
        ax[0].set_ylabel("reviews / week")
        ax[0].legend(fontsize=8)
        ax[0].grid(alpha=.3)
        t = trend.copy()
        for c in t.columns:
            ax[1].plot(t.index, t[c], marker="o", ms=3, label=str(c))
        ax[1].axvline(EVENT, ls="--", c="k", lw=1)
        ax[1].set_title("(b) Apollon: mean weekly reviews per seller, by group")
        ax[1].legend(fontsize=8)
        ax[1].grid(alpha=.3)
        for a_ in ax:
            a_.tick_params(axis="x", rotation=30)
        fig.suptitle("E1 - Cryptonia/Cannazon stop 2019-11-17/18; does activity "
                     "move to Apollon?", fontsize=10)
        fig.tight_layout(rect=[0, 0, 1, 0.93])
        for ext in ("png", "pdf"):
            fp = os.path.join(FIGDIR, "E1_social_substitution.%s" % ext)
            fig.savefig(fp, dpi=160)
            log("  wrote %s" % fp)
        plt.close(fig)
    except Exception:  # noqa: BLE001
        log("  !! figure failed:")
        for ln in traceback.format_exc().splitlines():
            log("     " + ln)

    # ----------------------------------------------------------- 7. verdict
    sep("7. VERDICT")
    b = out.get("Apollon")
    log("  What the aggregate shows: %s"
        % ", ".join("%s %+.0f%%" % (m, 100.0 * (R["aggregate"][m]["post_mean"]
                    / R["aggregate"][m]["pre_mean"] - 1))
                    for m in MARKETS if m in R["aggregate"]
                    and R["aggregate"][m]["pre_mean"] > 0))
    if b:
        log("  What the seller-level DiD shows on Apollon: beta=%+.4f, p=%.4g"
            % (b["beta"], b["p"]))
    log("")
    log("  The verdict is written into the stage report, not here, because the")
    log("  placebo has to be read next to the estimate. What this run fixes is")
    log("  that both numbers now exist.")

    R["did"] = out
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "14_E1_social_substitution.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    with open(os.path.join(RESULTS, "14_E1_social_substitution.json"), "w",
              encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, default=str)
    log("\nwrote %s/14_E1_social_substitution.{txt,json}" % RESULTS)
    log("E1_DONE")


if __name__ == "__main__":
    sys.exit(main())
