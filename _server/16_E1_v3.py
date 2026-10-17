#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""16_E1_v3.py -- E1, third pass. Two specific defects in v2, and both were mine.

Defect 1 (section C of v2 was underpowered by construction). The candidate set was
`apollon_pre & (dead_pre | empire_pre)` -- Apollon-active AND active in some other
market. That silently excluded every seller who traded on Apollon and nothing else,
which is most of the control group, and left 16 controls against 158 treated. The
crosstab printed 3/11, 1/31, 4/40, 8/76 and the imbalance was visible in it; the
significance test was not the thing that was wrong. Candidate set is now every
seller Apollon-active before the event, treated = also active in Cryptonia/Cannazon.

Defect 2 (the placebo in v2's section B could not discriminate). Entry into
Apollon was 0/237 and 0/436 in both placebo windows -- because Apollon barely
existed in 2019-07 and 2019-09 (it starts 2019-03-31 and runs at ~100-500
reviews/week). A test whose placebo has no room to move is not a test. The
placebo is replaced by the falsification the design actually needs:

  **entry into Empire.** Empire is a market that was *declining* over the same
  weeks. If sellers exposed to the dead markets also enter Empire at a higher rate,
  then what B measures is a general propensity of those sellers to appear in new
  markets, not reallocation caused by the shock. Migration has to be directed: it
  should show up at the market that absorbed the volume and not at the market that
  was draining. If the effect is the same at both, E1 has measured seller
  expansiveness and must say so.

This matters because the two explanations are not variants of each other. Under
substitution the ecosystem reallocates and continues; under "exposed sellers are
simply more mobile people", the ecosystem is not resilient -- it is a different
population doing a different thing, and the survival of total volume is a
selection artefact.

Everything else -- the aggregate in section A, the fact that a collector
re-weighting remains observationally equivalent there -- is unchanged and still
stands.
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
        lo = float(beta - st.t.ppf(0.975, G - 1) * se)
        hi = float(beta + st.t.ppf(0.975, G - 1) * se)
    except Exception:  # noqa: BLE001
        p, lo, hi = float("nan"), float("nan"), float("nan")
    return {"beta": beta, "se": se, "t": t, "p": p, "lo": lo, "hi": hi,
            "n": int(len(d)), "n_clusters": int(G)}


def entry_rate(pre, post, target, exposure="dead"):
    """Among sellers naive to `target` before the event, who enters it after?"""
    tgt_pre = set(pre.loc[pre["market"] == target, "vendor"])
    tgt_post = set(post.loc[post["market"] == target, "vendor"])
    dead_pre = set(pre.loc[pre["market"].isin(DEAD), "vendor"])
    other = sorted(set(MARKETS) - set(DEAD) - {target})
    ctrl_src = set(pre.loc[pre["market"].isin(other), "vendor"])
    exposed = dead_pre - tgt_pre
    control = ctrl_src - tgt_pre - dead_pre
    e = len(exposed & tgt_post)
    c = len(control & tgt_post)
    out = {"target": target, "exposed_n": len(exposed), "exposed_entered": e,
           "control_n": len(control), "control_entered": c,
           "exposed_rate": 100.0 * e / max(len(exposed), 1),
           "control_rate": 100.0 * c / max(len(control), 1)}
    try:
        from scipy import stats as st
        orr, pv = st.fisher_exact([[e, len(exposed) - e], [c, len(control) - c]])
        out["odds_ratio"] = float(orr)
        out["fisher_p"] = float(pv)
    except Exception:  # noqa: BLE001
        pass
    return out


def main():
    log("=" * 78)
    log("E1 v3 -- DIRECTED MIGRATION, OR JUST MOBILE SELLERS?")
    log("=" * 78)

    ks = pd.read_parquet(os.path.join(WORK, "kilos_reviews.parquet"))
    ts = pd.to_datetime(pd.to_numeric(ks["f2"], errors="coerce"), unit="s",
                        errors="coerce")
    d = ks.assign(ts=ts, market=ks["market"].astype(str).str.strip(),
                  vendor=ks["vendor"].astype(str).str.strip())
    d = d[d["market"].isin(MARKETS) & d["ts"].notna()]
    d = d[(d["vendor"] != "") & (d["vendor"].str.lower() != "nan")]
    d["week"] = d["ts"].dt.to_period("W").dt.start_time

    pre_d = d[(d["ts"] >= PRE0) & (d["ts"] < EVENT)]
    post_d = d[(d["ts"] >= EVENT) & (d["ts"] <= POST1)]

    # ================================ A. the falsification section B needs
    sep("A. Is entry DIRECTED at the market that grew, or general?")
    log("  Outcome: among sellers with no history in the target market, who")
    log("  appears there after the shock. Same definition for every target, so the")
    log("  rows are comparable to each other.")
    log("")
    log("  %-11s %8s %8s %8s %8s %10s %8s" %
        ("target", "exp n", "exp %", "ctl n", "ctl %", "OR", "p"))
    res = []
    for target in ["Apollon", "CannaHome", "Empire"]:
        o = entry_rate(pre_d, post_d, target)
        res.append(o)
        log("  %-11s %8d %7.1f%% %8d %7.1f%% %10.3f %8.4g"
            % (target, o["exposed_n"], o["exposed_rate"], o["control_n"],
               o["control_rate"], o.get("odds_ratio", float("nan")),
               o.get("fisher_p", float("nan"))))
    R["entry_by_target"] = res
    log("")
    log("  Apollon and CannaHome are the markets that GREW (+836%, +358%).")
    log("  Empire is the market that SHRANK (-62%). If the exposed sellers enter")
    log("  all three at the same elevated rate, the effect is seller mobility and")
    log("  not substitution.")
    ap = [o for o in res if o["target"] == "Apollon"][0]
    em = [o for o in res if o["target"] == "Empire"][0]
    log("")
    log("  entry-rate gap (exposed - control):  Apollon %+.1f pp ; Empire %+.1f pp"
        % (ap["exposed_rate"] - ap["control_rate"],
           em["exposed_rate"] - em["control_rate"]))
    R["directedness"] = {"apollon_gap_pp": ap["exposed_rate"] - ap["control_rate"],
                         "empire_gap_pp": em["exposed_rate"] - em["control_rate"]}

    # ============================================ B. entry, per market pair
    sep("B. Entry into Apollon, split by which dead market the seller was on")
    for src in ["Cryptonia", "Cannazon"]:
        s = set(pre_d.loc[pre_d["market"] == src, "vendor"])
        tgt_pre = set(pre_d.loc[pre_d["market"] == "Apollon", "vendor"])
        tgt_post = set(post_d.loc[post_d["market"] == "Apollon", "vendor"])
        others = set(pre_d.loc[pre_d["market"].isin(["Empire", "CannaHome"]), "vendor"])
        ex = s - tgt_pre
        ct = others - tgt_pre - set(pre_d.loc[pre_d["market"].isin(DEAD), "vendor"])
        e, c = len(ex & tgt_post), len(ct & tgt_post)
        try:
            from scipy import stats as st
            orr, pv = st.fisher_exact([[e, len(ex) - e], [c, len(ct) - c]])
            log("  %-10s-only sellers: %d/%d (%.1f%%) vs control %d/%d (%.1f%%)  "
                "OR=%.3f p=%.4g" % (src, e, len(ex), 100.0 * e / max(len(ex), 1),
                                    c, len(ct), 100.0 * c / max(len(ct), 1), orr, pv))
        except Exception:  # noqa: BLE001
            log("  %-10s-only sellers: %d/%d vs control %d/%d"
                % (src, e, len(ex), c, len(ct)))

    # ============================ C. intensive DiD, candidate set corrected
    sep("C. Intensive DiD -- candidate set corrected (all Apollon-active sellers)")
    ap = d[d["market"] == "Apollon"].copy()
    weeks = pd.date_range(PRE0, POST1, freq="W-MON")
    apollon_pre = set(pre_d.loc[pre_d["market"] == "Apollon", "vendor"])
    dead_pre = set(pre_d.loc[pre_d["market"].isin(DEAD), "vendor"])
    cand = sorted(apollon_pre)
    base_ap = pre_d[pre_d["market"] == "Apollon"].groupby("vendor").size()
    meta = pd.DataFrame({"seller": cand,
                         "base_ap": [int(base_ap.get(v, 0)) for v in cand]})
    meta["treat"] = meta["seller"].isin(dead_pre).astype(int)

    def stratum(n):
        return "s0" if n <= 0 else "s1" if n == 1 else "s2" if n <= 3 else \
               "s3" if n <= 9 else "s4"
    meta["stratum"] = meta["base_ap"].map(stratum)
    log("  sellers Apollon-active pre-event: %d" % len(meta))
    log("")
    log("  baseline-Apollon stratum x treatment (this is the table whose previous")
    log("  version showed the imbalance: 3/11, 1/31, 4/40, 8/76):")
    ct_ = pd.crosstab(meta["stratum"], meta["treat"])
    ct_.columns = ["control", "treated"]
    log(ct_.to_string())

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
    log("")
    log("  panel: %d sellers x %d weeks = %d rows"
        % (panel["seller"].nunique(), panel["week"].nunique(), len(panel)))

    m0 = fe_did(panel, "did", fes=("seller", "week"))
    m1 = fe_did(panel, "did", fes=("seller", "week", "sw"))
    log("")
    log("  (i)  seller + week FE    : beta=%+.4f se=%.4f t=%.2f p=%.4g  "
        "95%% CI [%+.3f, %+.3f]" % (m0["beta"], m0["se"], m0["t"], m0["p"],
                                    m0["lo"], m0["hi"]))
    log("  (ii) + stratum x week FE : beta=%+.4f se=%.4f t=%.2f p=%.4g  "
        "95%% CI [%+.3f, %+.3f]" % (m1["beta"], m1["se"], m1["t"], m1["p"],
                                    m1["lo"], m1["hi"]))
    pre_mean = panel.loc[(panel["post"] == 0) & (panel["treat"] == 1), "y"].mean()
    log("")
    log("  treated pre-period mean: %.2f reviews/week; the CI above is in the same")
    log("  units, so compare its width to that level, not to zero." % pre_mean)
    R["did"] = {"seller_week": m0, "plus_stratum_week": m1,
                "treated_pre_mean": float(pre_mean)}

    log("")
    log("  PLACEBO on model (ii), pre-period data only:")
    plac = []
    for when in ["2019-08-05", "2019-09-02", "2019-10-07"]:
        ev = pd.Timestamp(when)
        p2 = panel[panel["week"] < EVENT].copy()
        p2["post"] = (p2["week"] >= ev).astype(int)
        p2["did"] = p2["treat"] * p2["post"]
        mm = fe_did(p2, "did", fes=("seller", "week", "sw"))
        if mm:
            plac.append({"event": when, "beta": mm["beta"], "p": mm["p"],
                         "lo": mm["lo"], "hi": mm["hi"]})
            log("    %s: beta=%+.4f p=%.4g  95%% CI [%+.3f, %+.3f]"
                % (when, mm["beta"], mm["p"], mm["lo"], mm["hi"]))
    R["placebo"] = plac

    # --------------------------------------------------------------- figure
    sep("D. Figure")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        os.makedirs(FIGDIR, exist_ok=True)
        fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
        names = [o["target"] for o in res]
        ex = [o["exposed_rate"] for o in res]
        ctl = [o["control_rate"] for o in res]
        x = np.arange(len(names))
        ax[0].bar(x - 0.2, ex, 0.4, label="exposed (Cryptonia/Cannazon)", color="#c44")
        ax[0].bar(x + 0.2, ctl, 0.4, label="control", color="#48a")
        ax[0].set_xticks(x)
        ax[0].set_xticklabels(names)
        ax[0].set_ylabel("% entering the target market")
        ax[0].set_title("(a) Entry by target market\ndirected, or general mobility?")
        ax[0].legend(fontsize=8)
        for i, (a_, b_) in enumerate(zip(ex, ctl)):
            ax[0].text(i - 0.2, a_, "%.1f" % a_, ha="center", va="bottom", fontsize=8)
            ax[0].text(i + 0.2, b_, "%.1f" % b_, ha="center", va="bottom", fontsize=8)

        piv = d.pivot_table(index="week", columns="market", values="price",
                            aggfunc="size", fill_value=0)
        piv["TOTAL"] = piv.sum(axis=1)
        for m in MARKETS:
            ax[1].plot(piv.index, piv[m], marker="o", ms=3, label=m)
        ax[1].plot(piv.index, piv["TOTAL"], ls="--", c="k", lw=1.5, label="TOTAL")
        ax[1].axvline(EVENT, ls=":", c="r", lw=1.2)
        ax[1].set_title("(b) Weekly reviews by market\ntotal preserved, composition "
                        "turned over")
        ax[1].legend(fontsize=8)

        tr = panel.groupby(["week", "treat"])["y"].mean().unstack()
        for c_ in tr.columns:
            ax[2].plot(tr.index, tr[c_], marker="o", ms=3,
                       label=("exposed" if c_ == 1 else "control"))
        ax[2].axvline(EVENT, ls=":", c="r", lw=1.2)
        ax[2].set_title("(c) Apollon reviews per seller\n(intensive margin, "
                        "balancing on baseline level)")
        ax[2].legend(fontsize=8)
        for a_ in ax:
            a_.grid(alpha=.3)
            a_.tick_params(axis="x", rotation=30)
        fig.suptitle("E1 v3 - Cryptonia/Cannazon stop 2019-11-17/18", fontsize=10)
        fig.tight_layout(rect=[0, 0, 1, 0.92])
        for ext in ("png", "pdf"):
            fp = os.path.join(FIGDIR, "E1_social_substitution_v3.%s" % ext)
            fig.savefig(fp, dpi=160)
            log("  wrote %s" % fp)
        plt.close(fig)
    except Exception:  # noqa: BLE001
        log("  !! figure failed:")
        for ln in traceback.format_exc().splitlines():
            log("     " + ln)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "16_E1_v3.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    with open(os.path.join(RESULTS, "16_E1_v3.json"), "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, default=str)
    log("\nwrote %s/16_E1_v3.{txt,json}" % RESULTS)
    log("E1V3_DONE")


if __name__ == "__main__":
    sys.exit(main())
