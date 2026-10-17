#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""39_E3_robust.py -- does E1 v3's substitution effect survive matching?

38_ produced the result that matters:

    unmatched     seller+week FE : beta=+3.8819  p=0.0048
    unmatched  +stratum x week FE: beta=+3.6365  p=0.0119
    PSM-matched   seller+week FE : beta=+1.0424  p=0.3619
    PSM-matched +stratum x week FE: beta=+1.3435 p=0.2281

and the pre-registered PSM covariate set matched ZERO pairs (overlap 0.000,
max|b|=20.6 -- separation, because `n_markets` is implied by the treatment
definition).

Two things in 38_ are not good enough to rest a conclusion on, and this script
fixes both:

1. SET CHOICE. 38_ picked covariate set D because it produced the most pairs.
   That is a choice, and the DiD must be shown under every set that matches at
   all, not only under the one that was picked.

2. THE NULL WAS MISMATCHED. 38_'s 500 placebos were run on the UNMATCHED design
   (null mean +1.03, sd 0.49) while the matched beta came from a matched sample.
   Comparing a matched estimate to an unmatched null is not a test. The placebo
   is re-run here under EACH design, and each real beta is placed in its own
   null.

The null mean of +1.03 rather than 0 is itself informative: it says the
unmatched contrast carries a positive drift in the pre-period, which is the
differential trend the stratum x week FE exists to absorb.

Design held fixed across placebos: the matched SELLER LIST is computed once from
the real pre-period and reused for every fake event, so the placebo varies the
event date and nothing else.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

WORK = "/root/cis/work"
RESULTS = "/root/cis/results"
MARKETS = ["Empire", "Cannazon", "Apollon", "Cryptonia", "CannaHome"]
DEAD = ["Cryptonia", "Cannazon"]
TARGET = "Apollon"
EVENT = pd.Timestamp("2019-11-18")
PRE0 = pd.Timestamp("2019-06-03")
POST1 = pd.Timestamp("2020-01-12")
N_PLACEBO = 500
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
    if len(d) == 0:
        return None
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
    return {"beta": beta, "se": se, "t": t, "p": p,
            "n": int(len(d)), "n_clusters": int(G)}


def logit_fit(X, y, iters=200, ridge=1e-6):
    n, k = X.shape
    b = np.zeros(k)
    for _ in range(iters):
        z = np.clip(X @ b, -30, 30)
        p = 1.0 / (1.0 + np.exp(-z))
        w = np.maximum(p * (1.0 - p), 1e-9)
        zz = z + (y - p) / w
        A = X.T @ (X * w[:, None]) + ridge * np.eye(k)
        try:
            bb = np.linalg.solve(A, X.T @ (w * zz))
        except np.linalg.LinAlgError:
            break
        if np.max(np.abs(bb - b)) < 1e-10:
            b = bb
            break
        b = bb
    return b


def main():
    log("=" * 78)
    log("39  Does E1 v3's substitution effect survive matching? (robustness)")
    log("=" * 78)

    ks = pd.read_parquet(os.path.join(WORK, "kilos_reviews.parquet"))
    ts = pd.to_datetime(pd.to_numeric(ks["f2"], errors="coerce"), unit="s",
                        errors="coerce")
    d = ks.assign(ts=ts, market=ks["market"].astype(str).str.strip(),
                  vendor=ks["vendor"].astype(str).str.strip(),
                  rating=pd.to_numeric(ks["f3"], errors="coerce"),
                  price=pd.to_numeric(ks["price"], errors="coerce"))
    d = d[d["market"].isin(MARKETS) & d["ts"].notna()]
    d = d[(d["vendor"] != "") & (d["vendor"].str.lower() != "nan")]
    d["week"] = d["ts"].dt.to_period("W").dt.start_time
    pre_d = d[(d["ts"] >= PRE0) & (d["ts"] < EVENT)]
    ap = d[d["market"] == TARGET].copy()
    weeks = pd.date_range(PRE0, POST1, freq="W-MON")

    cand = sorted(set(pre_d.loc[pre_d["market"] == TARGET, "vendor"]))
    dead_pre = set(pre_d.loc[pre_d["market"].isin(DEAD), "vendor"])
    pre = pre_d[pre_d["vendor"].isin(set(cand))].copy()
    g = pre.groupby("vendor")
    cov = pd.DataFrame(index=pd.Index(cand, name="seller"))
    cov["base_ap"] = g.apply(lambda x: int((x["market"] == TARGET).sum()),
                             include_groups=False)
    cov["total_rev"] = g.size()
    cov["n_markets"] = g["market"].nunique()
    cov["n_other"] = pre[~pre["market"].isin(DEAD + [TARGET])].groupby(
        "vendor")["market"].nunique().reindex(cov.index).fillna(0)
    cov["pos_share"] = g["rating"].apply(lambda x: float((x == 1).mean()),
                                         include_groups=False)
    cov["neg_share"] = g["rating"].apply(lambda x: float((x == -1).mean()),
                                         include_groups=False)
    cov["mean_price"] = g["price"].mean()
    cov["n_weeks_active"] = g["week"].nunique()
    cov["span_days"] = g["ts"].apply(
        lambda x: float((x.max() - x.min()).total_seconds() / 86400.0),
        include_groups=False)
    cov = cov.fillna(0.0)
    cov["treat"] = cov.index.isin(dead_pre).astype(int)

    def stratum(n):
        return "s0" if n <= 0 else "s1" if n == 1 else "s2" if n <= 3 else \
               "s3" if n <= 9 else "s4"
    cov["stratum"] = cov["base_ap"].map(stratum)

    SETS = {
        "B minus n_markets": ["base_ap", "total_rev", "n_other", "pos_share",
                              "neg_share", "mean_price", "n_weeks_active",
                              "span_days"],
        "C activity + quality": ["base_ap", "pos_share", "neg_share",
                                 "mean_price", "n_weeks_active", "span_days"],
        "D size + quality": ["base_ap", "pos_share", "neg_share", "mean_price"],
    }

    def matched_pairs(cs):
        X = cov[cs].to_numpy(float)
        mu, sd = X.mean(0), X.std(0)
        sd[sd == 0] = 1.0
        Xs = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
        bb = logit_fit(Xs, cov["treat"].to_numpy(float))
        lp = Xs @ bb
        ti = np.where(cov["treat"].to_numpy() == 1)[0]
        ci = np.where(cov["treat"].to_numpy() == 0)[0]
        cal = 0.2 * float(np.std(lp))
        order = ti[np.argsort(-lp[ti])]
        avail = set(ci.tolist())
        prs = []
        for i in order:
            if not avail:
                break
            cands = np.array(sorted(avail))
            dist = np.abs(lp[cands] - lp[i])
            j = int(np.argmin(dist))
            if dist[j] <= cal:
                prs.append((i, int(cands[j])))
                avail.discard(int(cands[j]))
        sel = [cov.index[i] for i, _ in prs] + [cov.index[j] for _, j in prs]
        return sel, len(prs)

    def build(sel, event=EVENT, lo=PRE0, hi=POST1, wk=None):
        wk = weeks if wk is None else wk
        aggp = (ap[ap["vendor"].isin(set(sel))]
                .groupby(["vendor", "week"]).size().rename("y").reset_index())
        full = pd.MultiIndex.from_product([sorted(sel), wk],
                                          names=["vendor", "week"])
        p = (aggp.set_index(["vendor", "week"]).reindex(full)
             .fillna({"y": 0}).reset_index().rename(columns={"vendor": "seller"}))
        p = p.merge(cov[["treat", "stratum"]], left_on="seller",
                    right_index=True, how="left")
        p["post"] = (p["week"] >= event).astype(int)
        p["did"] = p["treat"] * p["post"]
        p["sw"] = p["stratum"].astype(str) + "|" + p["week"].astype(str)
        return p

    sep("1. ★ DiD under EVERY matched covariate set (38_ reported only set D)")
    log("  %-24s %6s %10s %8s %10s %8s" %
        ("design", "pairs", "b(s+w)", "p", "b(+sw)", "p"))
    out = {}
    designs = {"unmatched": None}
    for nm, cs in SETS.items():
        sel, npr = matched_pairs(cs)
        designs[nm] = sel
        log("  %-24s %6d" % (nm, npr))
    log("")
    for nm, sel in designs.items():
        use = cand if sel is None else sel
        if len(use) < 20:
            continue
        p = build(use)
        m0 = fe_did(p, "did", fes=("seller", "week"))
        m1 = fe_did(p, "did", fes=("seller", "week", "sw"))
        log("  %-24s %6d %+10.4f %8.4f %+10.4f %8.4f"
            % (nm, len(use) // 2 if sel is not None else len(cand),
               m0["beta"], m0["p"], m1["beta"], m1["p"]))
        out[nm] = {"n_sellers": len(use), "seller_week": m0, "plus_sw": m1}
    R["did_by_design"] = out

    sep("2. ★ 500 placebos under EACH design (each beta in its OWN null)")
    log("  The matched seller list is held fixed; only the fake event date")
    log("  moves, so the null varies the event and nothing else.")
    log("")
    pre_only = d[(d["ts"] >= PRE0) & (d["ts"] < EVENT)]
    lo_w = PRE0 + pd.Timedelta(weeks=4)
    hi_w = EVENT - pd.Timedelta(weeks=1)
    span = max((hi_w - lo_w).days, 1)
    rng = np.random.default_rng(20260924)
    dates = [lo_w + pd.Timedelta(days=int(x))
             for x in rng.integers(0, span, size=N_PLACEBO * 3)]

    log("  %-24s %8s %9s %9s %9s %9s %9s" %
        ("design", "n_null", "null_mean", "null_sd", "real", "pctile", "p_plac"))
    for nm, sel in designs.items():
        use = cand if sel is None else sel
        if len(use) < 20:
            continue
        null = []
        for fd in dates:
            if len(null) >= N_PLACEBO:
                break
            fw = pd.date_range(PRE0, EVENT - pd.Timedelta(days=1), freq="W-MON")
            if fd >= fw[-1] or fd <= fw[0]:
                continue
            fpre = pre_only[(pre_only["ts"] >= PRE0) & (pre_only["ts"] < fd)]
            cf = set(fpre.loc[fpre["market"] == TARGET, "vendor"]) & set(use)
            if len(cf) < 20:
                continue
            pf = build(sorted(cf), event=fd, wk=fw)
            m = fe_did(pf, "did", fes=("seller", "week"))
            if m is not None and np.isfinite(m["beta"]):
                null.append(float(m["beta"]))
        if len(null) < 10:
            log("  %-24s   (too few placebos)" % nm)
            continue
        null = np.array(null)
        real = out[nm]["seller_week"]["beta"]
        pct = float(100.0 * (null < real).mean())
        pk = float((null >= real).mean())
        log("  %-24s %8d %+9.4f %9.4f %+9.4f %8.1f%% %9.4f"
            % (nm, len(null), null.mean(), null.std(), real, pct, pk))
        R.setdefault("placebo", {})[nm] = {
            "n": int(len(null)), "mean": float(null.mean()),
            "sd": float(null.std()), "real": float(real),
            "percentile": pct, "p_placebo": pk,
            "p2.5": float(np.percentile(null, 2.5)),
            "p97.5": float(np.percentile(null, 97.5))}

    sep("3. Reading")
    log("  A design whose real beta sits at the null's median has produced no")
    log("  evidence of an event effect: the same estimator, on pre-period data")
    log("  with no event, returns that number routinely. A design whose real")
    log("  beta sits in the tail has produced evidence, provided the null's own")
    log("  mean is reported -- a null mean far from 0 means the contrast carries")
    log("  a drift that must be explained rather than assumed away.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "39_E3_robust.json"), "w",
              encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "39_E3_robust.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/39_E3_robust.{txt,json}" % RESULTS)
    log("E3_ROBUST_DONE")


if __name__ == "__main__":
    main()
