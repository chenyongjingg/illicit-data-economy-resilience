#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""15_E1_social_substitution_v2.py -- E1, rebuilt because v1 failed its own placebo.

What went wrong in v1, kept here because it is the reason for every choice below
--------------------------------------------------------------------------------
v1 estimated a seller-level DiD on Apollon and got beta = -1.3364, p = 0.0118.
It also ran the same DiD at three dates when nothing happened and got
-1.1478 (p=0.083), -1.6909 (p=0.0028) and -1.6556 (p=0.0020). **The placebo
estimates are larger, and more significant, than the estimate for the event they
are supposed to be placebos for.** The design was measuring a pre-existing
differential trend.

The trend table says why, in one line: the control group was defined as "active
in Apollon before the event", so 331/331 of them are Apollon-active by
construction, while only 158/697 of the treated group are. Their mean weekly
Apollon reviews run 0.178 -> 2.816 across the pre-period against the treated
group's 0.099 -> 0.937. Two groups selected to differ in level will differ in
trend, because count outcomes have variance that scales with the mean. The DiD
was never comparing like with like.

Three fixes, each aimed at one specific defect
---------------------------------------------
A. Aggregate: total volume and composition. Descriptive only, and labelled so.
   The v1 aggregate (Apollon +836%, Cryptonia/Cannazon -100%) cannot distinguish
   substitution from a collector re-weighting its coverage, and neither can this
   one. It is reported as a description, never as an effect.

B. Extentive margin, symmetric by construction. Restrict to sellers who had ZERO
   Apollon reviews before the event, so both groups start at the same point --
   zero. Exposed = active in Cryptonia/Cannazon; control = active in Empire only.
   Both were trading in the same ecosystem over the same weeks. The outcome is
   whether they appear in Apollon at all afterwards. A seller with no Apollon
   history who acquires one can only have arrived, so this statistic is not a
   change in how often anyone writes reviews. v1 could not test this, because its
   control group had no room to enter.

C. Intensive margin, with the scale artefact removed rather than assumed away.
   Restrict to sellers Apollon-active before the event, then allow every baseline
   intensity stratum its own week effects (stratum x week FE). Any differential
   trend that is a function of baseline size -- the exact thing that broke v1 --
   is absorbed by those effects. What survives is a change in the gap *within*
   comparable sellers. The same three placebos are re-run; if they are still as
   large as the event estimate, this design fails too and it is reported as a
   failure.

Limits that no redesign removes:
  * treatment is a **handle match**, and `11_` found no key tying a handle to a
    person. Sellers who changed handle are misfiled as controls, which attenuates.
    A positive result survives that; a null does not distinguish "nobody moved"
    from "people moved and changed their name".
  * the collector could have re-weighted coverage, which is observationally
    equivalent at the aggregate level. Only B and C speak to it, and only partly.
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
DEAD = ["Cryptonia", "Cannazon"]
EVENT = pd.Timestamp("2019-11-18")
PRE0 = pd.Timestamp("2019-06-03")
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


def demean(y, *fid):
    """Residualise y on the additive effects of every factor in fid."""
    yr = y - y.mean()
    counts = [np.bincount(f, minlength=f.max() + 1) for f in fid]
    for _ in range(80):
        prev = yr.copy()
        for f, c in zip(fid, counts):
            m = np.bincount(f, yr, minlength=len(c)) / np.maximum(c, 1)
            yr = yr - m[f]
        if np.max(np.abs(yr - prev)) < 1e-11:
            break
    return yr


def fe_did(d, xcol, ycol="y", fes=("seller", "week"), cl="seller"):
    """OLS on residualised y and x with cluster-robust SEs by `cl`."""
    y = d[ycol].to_numpy(float)
    fid = [pd.factorize(d[c])[0] for c in fes]
    yr = demean(y, *fid)
    xr = demean(d[xcol].to_numpy(float), *fid)
    denom = float(xr @ xr)
    if denom <= 0:
        return None
    beta = float(xr @ yr) / denom
    resid = yr - beta * xr
    sid = pd.factorize(d[cl])[0]
    meat = 0.0
    for g in np.unique(sid):
        m = sid == g
        sg = float(xr[m] @ resid[m])
        meat += sg * sg
    G = len(np.unique(sid))
    se = float(np.sqrt(meat * (G / max(G - 1.0, 1.0))) / denom)
    t = beta / se if se > 0 else np.nan
    try:
        from scipy import stats as st
        p = float(2 * st.t.sf(abs(t), G - 1))
    except Exception:  # noqa: BLE001
        p = float("nan")
    return {"beta": beta, "se": se, "t": t, "p": p, "n": int(len(d)),
            "n_clusters": int(G)}


def main():
    log("=" * 78)
    log("E1 v2 -- DOES ACTIVITY MOVE TO A SURVIVING MARKET WHEN OTHERS DIE?")
    log("=" * 78)
    R["event"] = str(EVENT.date())

    ks = pd.read_parquet(os.path.join(WORK, "kilos_reviews.parquet"))
    ts = pd.to_datetime(pd.to_numeric(ks["f2"], errors="coerce"), unit="s",
                        errors="coerce")
    d = ks.assign(ts=ts, market=ks["market"].astype(str).str.strip(),
                  vendor=ks["vendor"].astype(str).str.strip())
    d = d[d["market"].isin(MARKETS) & d["ts"].notna()]
    d = d[(d["vendor"] != "") & (d["vendor"].str.lower() != "nan")]

    # ============================================== A. the aggregate, descriptive
    sep("A. Aggregate: total volume and composition (DESCRIPTIVE ONLY)")
    d["week"] = d["ts"].dt.to_period("W").dt.start_time
    piv = d.pivot_table(index="week", columns="market", values="price",
                        aggfunc="size", fill_value=0)
    piv["TOTAL"] = piv.sum(axis=1)
    show = piv.loc[(piv.index >= "2019-10-07") & (piv.index <= "2020-01-07")]
    log("")
    log(show.to_string())
    pre = (piv.index >= PRE0) & (piv.index < EVENT)
    post = (piv.index >= EVENT) & (piv.index <= POST1)
    log("")
    log("  weekly mean, pre (2019-06-03..2019-11-11) vs post (2019-11-18..):")
    for m in list(MARKETS) + ["TOTAL"]:
        a, b = piv.loc[pre, m].mean(), piv.loc[post, m].mean()
        log("    %-11s %8.1f -> %8.1f  (%+.0f%%)" % (m, a, b, 100.0 * (b / a - 1) if a else float("nan")))
    tot_pre, tot_post = piv.loc[pre, "TOTAL"].mean(), piv.loc[post, "TOTAL"].mean()
    log("")
    log("  TOTAL ecosystem volume: %.0f -> %.0f (%+.0f%%)"
        % (tot_pre, tot_post, 100.0 * (tot_post / tot_pre - 1)))
    log("  shares of total, pre -> post:")
    for m in MARKETS:
        log("    %-11s %5.1f%% -> %5.1f%%"
            % (m, 100.0 * piv.loc[pre, m].mean() / tot_pre,
               100.0 * piv.loc[post, m].mean() / tot_post))
    R["aggregate"] = {"pre": {m: float(piv.loc[pre, m].mean()) for m in MARKETS},
                      "post": {m: float(piv.loc[post, m].mean()) for m in MARKETS},
                      "total_pre": float(tot_pre), "total_post": float(tot_post)}
    log("")
    log("  READ THIS AS A DESCRIPTION, NOT AN EFFECT. Two markets stop dead")
    log("  within a day of each other and the total is roughly preserved while the")
    log("  composition turns over. A collector that re-weighted which markets it")
    log("  scraped would produce this exact table with nobody moving. A and B/C")
    log("  are separated precisely because this table cannot do it alone.")

    # ==================================== B. symmetric entry into a live market
    sep("B. Entry into Apollon, among sellers with NO Apollon history")
    pre_d = d[(d["ts"] >= PRE0) & (d["ts"] < EVENT)]
    post_d = d[(d["ts"] >= EVENT) & (d["ts"] <= POST1)]

    apollon_pre = set(pre_d.loc[pre_d["market"] == "Apollon", "vendor"])
    apollon_post = set(post_d.loc[post_d["market"] == "Apollon", "vendor"])
    dead_pre = set(pre_d.loc[pre_d["market"].isin(DEAD), "vendor"])
    empire_pre = set(pre_d.loc[pre_d["market"] == "Empire", "vendor"])

    # both groups are Apollon-naive before the event: same starting point, zero
    exposed = dead_pre - apollon_pre
    control = empire_pre - apollon_pre - dead_pre
    log("  cell counts (all Apollon-naive before %s):" % EVENT.date())
    log("    exposed  (>=1 Cryptonia/Cannazon review pre): %d" % len(exposed))
    log("    control  (>=1 Empire review pre, no dead-market review): %d"
        % len(control))
    log("")
    for lbl, grp in (("exposed", exposed), ("control", control)):
        e = len(grp & apollon_post)
        log("    %-8s entered Apollon post-event: %4d / %4d  (%.1f%%)"
            % (lbl, e, len(grp), 100.0 * e / max(len(grp), 1)))
    e = len(exposed & apollon_post)
    c = len(control & apollon_post)
    n1, n0 = len(exposed), len(control)
    try:
        from scipy import stats as st
        tab = [[e, n1 - e], [c, n0 - c]]
        orr, pv = st.fisher_exact(tab)
        chi2, pchi, _, _ = st.chi2_contingency(tab, correction=False)
        log("")
        log("  Fisher exact: odds ratio %.3f, p = %.4g" % (orr, pv))
        log("  chi2 (no correction): %.1f, p = %.4g" % (chi2, pchi))
        R["entry"] = {"exposed_n": n1, "exposed_entered": e,
                      "control_n": n0, "control_entered": c,
                      "odds_ratio": float(orr), "fisher_p": float(pv)}
    except Exception:  # noqa: BLE001
        log("  !! scipy unavailable: %s" % traceback.format_exc().splitlines()[-1])
        R["entry"] = {"exposed_n": n1, "exposed_entered": e,
                      "control_n": n0, "control_entered": c}

    # placebo: move the window back, before anything happened
    log("")
    log("  PLACEBO, same test with the window shifted into a quiet period:")
    for ev, p0, p1 in [("2019-07-15", "2019-03-01", "2019-07-15"),
                       ("2019-09-15", "2019-05-01", "2019-09-15")]:
        evt, q0, q1 = pd.Timestamp(ev), pd.Timestamp(p0), pd.Timestamp(p1)
        a_pre = d[(d["ts"] >= q0) & (d["ts"] < evt)]
        a_post = d[(d["ts"] >= evt) & (d["ts"] <= q1)]
        ap = set(a_pre.loc[a_pre["market"] == "Apollon", "vendor"])
        ap2 = set(a_post.loc[a_post["market"] == "Apollon", "vendor"])
        dpre = set(a_pre.loc[a_pre["market"].isin(DEAD), "vendor"])
        epre = set(a_pre.loc[a_pre["market"] == "Empire", "vendor"])
        ex = dpre - ap
        ct = epre - ap - dpre
        ee, cc = len(ex & ap2), len(ct & ap2)
        try:
            from scipy import stats as st
            orr, pv = st.fisher_exact([[ee, len(ex) - ee], [cc, len(ct) - cc]])
            log("    event %s: exposed %d/%d (%.1f%%) vs control %d/%d (%.1f%%)  "
                "OR=%.3f p=%.3g"
                % (ev, ee, len(ex), 100.0 * ee / max(len(ex), 1), cc, len(ct),
                   100.0 * cc / max(len(ct), 1), orr, pv))
        except Exception:  # noqa: BLE001
            log("    event %s: exposed %d/%d vs control %d/%d"
                % (ev, ee, len(ex), cc, len(ct)))

    # ======================== C. intensive DiD with stratum x week fixed effects
    sep("C. Intensive DiD, baseline-intensity strata given their own week effects")
    ap = d[d["market"] == "Apollon"].copy()
    ap["week"] = ap["ts"].dt.to_period("W").dt.start_time
    weeks = pd.date_range(PRE0, POST1, freq="W-MON")

    pre_tot = (pre_d.groupby("vendor").size().rename("pre_total"))
    base_ap = (pre_d[pre_d["market"] == "Apollon"].groupby("vendor").size()
               .rename("base_ap"))
    cand = sorted((apollon_pre & (dead_pre | empire_pre)))
    base = pd.Series({v: int(base_ap.get(v, 0)) for v in cand})
    bal = pd.Series({v: int(pre_tot.get(v, 0)) for v in cand})

    def stratum(n):
        if n <= 0:
            return "s0"
        if n == 1:
            return "s1"
        if n <= 3:
            return "s2"
        if n <= 9:
            return "s3"
        return "s4"

    meta = pd.DataFrame({"seller": cand, "base_ap": base.reindex(cand).values,
                         "pre_total": bal.reindex(cand).values})
    meta["treat"] = meta["seller"].isin(dead_pre).astype(int)
    meta["stratum"] = meta["base_ap"].map(stratum)
    log("  candidate sellers Apollon-active pre-event: %d" % len(meta))
    log("  baseline-Apollon stratum x treatment:")
    log(pd.crosstab(meta["stratum"], meta["treat"]).to_string())

    aggp = (ap[ap["vendor"].isin(set(cand))]
            .groupby(["vendor", "week"]).size().rename("y").reset_index())
    full = pd.MultiIndex.from_product([cand, weeks], names=["vendor", "week"])
    panel = (aggp.set_index(["vendor", "week"]).reindex(full)
             .fillna({"y": 0}).reset_index())
    panel = panel.rename(columns={"vendor": "seller"}).merge(
        meta[["seller", "treat", "stratum"]], on="seller", how="left")
    panel["post"] = (panel["week"] >= EVENT).astype(int)
    panel["did"] = panel["treat"] * panel["post"]
    panel["sw"] = panel["stratum"].astype(str) + "|" + panel["week"].astype(str)
    log("  panel: %d sellers x %d weeks = %d rows"
        % (panel["seller"].nunique(), panel["week"].nunique(), len(panel)))

    m0 = fe_did(panel, "did", fes=("seller", "week"))
    log("")
    log("  (i) seller + week FE           : beta=%+.4f se=%.4f t=%.2f p=%.4g"
        % (m0["beta"], m0["se"], m0["t"], m0["p"]))
    m1 = fe_did(panel, "did", fes=("seller", "week", "sw"))
    log("  (ii) + stratum x week FE       : beta=%+.4f se=%.4f t=%.2f p=%.4g"
        % (m1["beta"], m1["se"], m1["t"], m1["p"]))
    log("")
    log("  (ii) is the model that matters. It lets each baseline-intensity group")
    log("  follow its own weekly path, so a differential trend that is merely a")
    log("  function of baseline size -- the thing that produced v1's apparent")
    log("  effect -- is absorbed rather than attributed to the shock.")

    log("")
    log("  PLACEBO on model (ii):")
    plac = []
    for when in ["2019-08-05", "2019-09-02", "2019-10-07"]:
        ev = pd.Timestamp(when)
        p2 = panel.copy()
        p2["post"] = (p2["week"] >= ev).astype(int)
        p2["did"] = p2["treat"] * p2["post"]
        p2 = p2[(p2["week"] < EVENT)]
        mm = fe_did(p2, "did", fes=("seller", "week", "sw"))
        if mm:
            plac.append({"event": when, "beta": mm["beta"], "p": mm["p"]})
            log("    placebo event %s (pre-period data only, n=%d): beta=%+.4f p=%.4g"
                % (when, mm["n"], mm["beta"], mm["p"]))
    R["placebo"] = plac
    log("")
    log("  If any placebo is comparable in size to the event estimate, model (ii)")
    log("  has not fixed the problem and E1 declines the claim.")
    R["did"] = {"seller_week": m0, "plus_stratum_week": m1}

    # ------------------------------------------------------------ figure
    sep("D. Figure")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        os.makedirs(FIGDIR, exist_ok=True)
        fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
        for m in MARKETS:
            ax[0].plot(piv.index, piv[m], marker="o", ms=3, label=m)
        ax[0].plot(piv.index, piv["TOTAL"], ls="--", c="k", lw=1.5, label="TOTAL")
        ax[0].axvline(EVENT, ls=":", c="r", lw=1.2)
        ax[0].set_title("(a) Weekly reviews by market")
        ax[0].legend(fontsize=8)
        ax[0].set_ylabel("reviews / week")

        rate = pd.Series({"exposed": 100.0 * e / max(len(exposed), 1),
                          "control": 100.0 * c / max(len(control), 1)})
        ax[1].bar(rate.index, rate.values, color=["#c44", "#48a"])
        ax[1].set_title("(b) Entry into Apollon among\nApollon-naive sellers")
        ax[1].set_ylabel("% who appear in Apollon post-event")
        for i, v in enumerate(rate.values):
            ax[1].text(i, v, "%.1f%%" % v, ha="center", va="bottom", fontsize=9)

        tr = panel.groupby(["week", "treat"])["y"].mean().unstack()
        for c_ in tr.columns:
            ax[2].plot(tr.index, tr[c_], marker="o", ms=3,
                       label=("exposed" if c_ == 1 else "control"))
        ax[2].axvline(EVENT, ls=":", c="r", lw=1.2)
        ax[2].set_title("(c) Apollon reviews per seller,\nby treatment")
        ax[2].legend(fontsize=8)
        for a_ in ax:
            a_.grid(alpha=.3)
            a_.tick_params(axis="x", rotation=30)
        fig.suptitle("E1 v2 - Cryptonia/Cannazon stop 2019-11-17/18", fontsize=10)
        fig.tight_layout(rect=[0, 0, 1, 0.92])
        for ext in ("png", "pdf"):
            fp = os.path.join(FIGDIR, "E1_social_substitution_v2.%s" % ext)
            fig.savefig(fp, dpi=160)
            log("  wrote %s" % fp)
        plt.close(fig)
    except Exception:  # noqa: BLE001
        log("  !! figure failed:")
        for ln in traceback.format_exc().splitlines():
            log("     " + ln)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "15_E1_social_substitution_v2.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    with open(os.path.join(RESULTS, "15_E1_social_substitution_v2.json"), "w",
              encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, default=str)
    log("\nwrote %s/15_E1_social_substitution_v2.{txt,json}" % RESULTS)
    log("E1V2_DONE")


if __name__ == "__main__":
    sys.exit(main())
