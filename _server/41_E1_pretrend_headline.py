#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""41_E1_pretrend_headline.py -- does E1 v3's HEADLINE design have a pre-trend?

Report 09 ran 500 placebos under each design, and every one of them used
fes=("seller","week") -- that is E1 v3's model (i).

E1 v3 *reports* model (ii): seller + week + stratum x week FE (report 04
section 6c, beta=+3.637, p=0.0119). Model (ii)'s placebo evidence is THREE
draws (2019-08-05/09-02/10-07 -> +0.465/+0.508/+0.761, largest p=0.128).

So the 500-placebo evidence in report 09 does NOT cover the design the plan
actually reports as its result. That is a gap in my own work, and it is the
gap that matters: model (ii) exists precisely to absorb the differential
trend that killed E1 v1, so the honest question is whether it succeeds.

This script runs the same 500 fake event dates under BOTH specifications for
every design, and places each real beta in its own null -- two nulls per
design, eight nulls total. Nothing else changes.

Control built in: the three placebo dates report 04 recorded for model (ii)
are re-run here exactly. If they do not reproduce +0.465/+0.508/+0.761, this
instrument and the one that wrote report 04 are not measuring the same thing
and the new numbers are void.
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
# report 04 section 6c, model (ii): the three placebos and their recorded betas
RECORDED = [("2019-08-05", 0.465), ("2019-09-02", 0.508), ("2019-10-07", 0.761)]
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


MODELS = [("i  seller+week", ("seller", "week")),
          ("ii +stratum x week", ("seller", "week", "sw"))]


def main():
    log("=" * 78)
    log("41  Does E1 v3's HEADLINE design (ii) carry a pre-trend?")
    log("=" * 78)
    log("  Report 09's 500 placebos covered model (i) only. Model (ii) -- the")
    log("  one report 04 reports -- rested on 3 draws. Both run here.")

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

    designs = {"unmatched": None}
    for nm, cs in SETS.items():
        sel, npr = matched_pairs(cs)
        designs[nm] = sel
    log("  designs: " + ", ".join(
        "%s(%s)" % (k, "all" if v is None else len(v) // 2)
        for k, v in designs.items()))

    # ---- 0. control: reproduce report 04's three recorded placebos ----------
    sep("0. CONTROL -- reproduce report 04 section 6c's three placebo betas")
    log("  Same dates, model (ii). If these do not come back as +0.465/+0.508/")
    log("  +0.761 then this instrument is not the one that wrote report 04 and")
    log("  nothing below is comparable to it.")
    ctrl_ok = True
    for ds, exp in RECORDED:
        fd = pd.Timestamp(ds)
        fw = pd.date_range(PRE0, EVENT - pd.Timedelta(days=1), freq="W-MON")
        pf = build(cand, event=fd, wk=fw)
        m = fe_did(pf, "did", fes=("seller", "week", "sw"))
        got = m["beta"] if m else float("nan")
        ok = abs(got - exp) < 0.05
        ctrl_ok = ctrl_ok and ok
        log("  placebo %s  recorded %+.3f  re-run %+.4f  %s"
            % (ds, exp, got, "OK" if ok else "*** MISMATCH ***"))
    R["control_reproduced"] = bool(ctrl_ok)
    log("")
    log("  CONTROL %s" % ("RECOVERED" if ctrl_ok else "FAILED -- stop reading"))

    # ---- 1. real betas under both models ------------------------------------
    sep("1. Real betas, both models (reproduces report 04 section 6c)")
    real = {}
    for nm, sel in designs.items():
        use = cand if sel is None else sel
        if len(use) < 20:
            continue
        p = build(use)
        row = {}
        for mn, fes in MODELS:
            m = fe_did(p, "did", fes=fes)
            row[mn] = m
            log("  %-22s %-20s beta=%+9.4f  se=%7.4f  p=%.4f"
                % (nm, mn, m["beta"], m["se"], m["p"]))
        real[nm] = row
    R["real"] = real

    # ---- 2. 500 placebos under both models ---------------------------------
    sep("2. 500 placebos under BOTH models (report 09 ran model (i) only)")
    pre_only = d[(d["ts"] >= PRE0) & (d["ts"] < EVENT)]
    lo_w = PRE0 + pd.Timedelta(weeks=4)
    hi_w = EVENT - pd.Timedelta(weeks=1)
    span = max((hi_w - lo_w).days, 1)
    rng = np.random.default_rng(20260924)
    dates = [lo_w + pd.Timedelta(days=int(x))
             for x in rng.integers(0, span, size=N_PLACEBO * 3)]
    fw = pd.date_range(PRE0, EVENT - pd.Timedelta(days=1), freq="W-MON")

    log("  %-22s %-20s %6s %10s %9s %10s %8s %9s"
        % ("design", "model", "n_null", "null_mean", "null_sd", "real",
           "pctile", "p_plac"))
    for nm, sel in designs.items():
        use = cand if sel is None else sel
        if len(use) < 20:
            continue
        nulls = {mn: [] for mn, _ in MODELS}
        for fd in dates:
            if all(len(nulls[mn]) >= N_PLACEBO for mn, _ in MODELS):
                break
            if fd >= fw[-1] or fd <= fw[0]:
                continue
            fpre = pre_only[(pre_only["ts"] >= PRE0) & (pre_only["ts"] < fd)]
            cf = set(fpre.loc[fpre["market"] == TARGET, "vendor"]) & set(use)
            if len(cf) < 20:
                continue
            pf = build(sorted(cf), event=fd, wk=fw)
            for mn, fes in MODELS:
                if len(nulls[mn]) >= N_PLACEBO:
                    continue
                m = fe_did(pf, "did", fes=fes)
                if m is not None and np.isfinite(m["beta"]):
                    nulls[mn].append(float(m["beta"]))
        for mn, _ in MODELS:
            a = np.array(nulls[mn])
            if len(a) < 10:
                log("  %-22s %-20s   (too few placebos)" % (nm, mn))
                continue
            rb = real[nm][mn]["beta"]
            pct = float(100.0 * (a < rb).mean())
            pk = float((a >= rb).mean())
            log("  %-22s %-20s %6d %+10.4f %9.4f %+10.4f %7.1f%% %9.4f"
                % (nm, mn, len(a), a.mean(), a.std(), rb, pct, pk))
            R.setdefault("placebo", {}).setdefault(nm, {})[mn] = {
                "n": int(len(a)), "mean": float(a.mean()), "sd": float(a.std()),
                "real": float(rb), "percentile": pct, "p_placebo": pk}

    sep("3. Reading")
    log("  If model (ii)'s null mean is also far from 0, then stratum x week FE")
    log("  did NOT remove the pre-trend that report 09 measured in model (i),")
    log("  and report 04's section 6c argument -- that the design absorbs the")
    log("  differential trend 'that is a function of baseline size' -- is not")
    log("  supported by its own 500-draw null. If it is near 0, model (ii) does")
    log("  what report 04 claims and the +3.64 stands on 500 draws, not 3.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "41_E1_pretrend_headline.json"), "w",
              encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "41_E1_pretrend_headline.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/41_E1_pretrend_headline.{txt,json}" % RESULTS)
    log("E1_PRETREND_DONE")


if __name__ == "__main__":
    main()
