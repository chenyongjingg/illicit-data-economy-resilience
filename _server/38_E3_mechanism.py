#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""38_E3_mechanism.py -- E3: mechanism attribution on the kilos panel.

Pre-registered as "PSM + DiD (H1-H4) + 500 placebo tests". Report 08 established
which of the four hypotheses have a substrate and which do not, BY MEASUREMENT:

    H1 decentralization      -> substrate present (kilos market labels, dated)
    H2 cross-layer bridging  -> substrate MEASURED ABSENT (report 08 §1); not run
    H3 functional redundancy -> no category column (C-45); not run, declared
    H4 raw centrality        -> substrate present (pre-event review volume)

So this script runs H1 and H4, and records H2/H3 as explicitly not-testable
rather than quietly dropping them.

The estimator is E1 v3's, copied verbatim (demean + fe_did, SE clustered on
seller), so the PSM-matched numbers are directly comparable to the unmatched
ones E1 v3 reported. Changing the estimator here would make the comparison
between matched and unmatched meaningless.

What is NEW relative to E1 v3:
  - propensity-score matching on pre-event observables, with balance reported
    before and after (E1 v3 reported a visible stratum imbalance: 3/11, 1/31,
    4/40, 8/76);
  - the H1 and H4 moderators as interactions with the DiD term;
  - 500 placebo event dates instead of 3.

The moderators are PRE-EVENT constants, so seller fixed effects absorb their
main effects and only the interaction with `did` is identified. They are centred
so the `did` coefficient reads as the effect at the average moderator value.
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


# ------------------------------------------------------- estimator (E1 v3, verbatim)
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


# ------------------------------------------------------------------ small logit
def logit_fit(X, y, iters=200, ridge=1e-6):
    """IRLS logistic regression. Hand-rolled so E3 does not depend on sklearn
    being present (a missing package would otherwise silently change the
    propensity model, and with it the matched sample)."""
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


def smd(t, c):
    mt, mc = np.mean(t), np.mean(c)
    st, sc = np.var(t), np.var(c)
    sp = np.sqrt((st + sc) / 2.0)
    return 0.0 if sp <= 0 else float((mt - mc) / sp)


def main():
    log("=" * 78)
    log("38  E3 mechanism attribution -- PSM + DiD, H1/H4 moderators, 500 placebos")
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
    post_d = d[(d["ts"] >= EVENT) & (d["ts"] <= POST1)]

    sep("1. Candidate set and pre-event covariates (identical to E1 v3 §C)")
    ap = d[d["market"] == TARGET].copy()
    weeks = pd.date_range(PRE0, POST1, freq="W-MON")
    apollon_pre = set(pre_d.loc[pre_d["market"] == TARGET, "vendor"])
    dead_pre = set(pre_d.loc[pre_d["market"].isin(DEAD), "vendor"])
    cand = sorted(apollon_pre)

    pre = pre_d[pre_d["vendor"].isin(set(cand))].copy()
    g = pre.groupby("vendor")
    cov = pd.DataFrame(index=pd.Index(cand, name="seller"))
    cov["base_ap"] = g.apply(lambda x: int((x["market"] == TARGET).sum()))
    cov["total_rev"] = g.size()
    cov["n_markets"] = g["market"].nunique()
    # decentralization WITHOUT the dead markets and without the target: a seller
    # who is in a dead market is `treated` by construction, so counting dead
    # markets inside the moderator would build the treatment into the moderator.
    cov["n_other"] = pre[~pre["market"].isin(DEAD + [TARGET])].groupby(
        "vendor")["market"].nunique().reindex(cov.index).fillna(0)
    cov["pos_share"] = g["rating"].apply(lambda x: float((x == 1).mean()))
    cov["neg_share"] = g["rating"].apply(lambda x: float((x == -1).mean()))
    cov["mean_price"] = g["price"].mean()
    cov["n_weeks_active"] = g["week"].nunique()
    cov["span_days"] = g["ts"].apply(
        lambda x: float((x.max() - x.min()).total_seconds() / 86400.0))
    cov = cov.fillna(0.0)
    cov["treat"] = cov.index.isin(dead_pre).astype(int)

    def stratum(n):
        return "s0" if n <= 0 else "s1" if n == 1 else "s2" if n <= 3 else \
               "s3" if n <= 9 else "s4"
    cov["stratum"] = cov["base_ap"].map(stratum)
    log("  sellers %s-active pre-event: %d  (treated %d / control %d)"
        % (TARGET, len(cov), int(cov["treat"].sum()),
           int((1 - cov["treat"]).sum())))
    log("")
    log("  pre-event covariate means by arm:")
    log("  %-16s %10s %10s %9s" % ("covariate", "control", "treated", "SMD"))
    COVS = ["base_ap", "total_rev", "n_markets", "n_other", "pos_share",
            "neg_share", "mean_price", "n_weeks_active", "span_days"]
    for c in COVS:
        t = cov.loc[cov["treat"] == 1, c].to_numpy(float)
        k = cov.loc[cov["treat"] == 0, c].to_numpy(float)
        log("  %-16s %10.4f %10.4f %+9.4f"
            % (c, k.mean(), t.mean(), smd(t, k)))
    log("")
    log("  baseline-%s stratum x treatment:" % TARGET)
    ct_ = pd.crosstab(cov["stratum"], cov["treat"])
    ct_.columns = ["control", "treated"]
    log(ct_.to_string())

    sep("2. PSM: propensity score and 1:1 nearest-neighbour matching")
    log("  The first attempt matched ZERO pairs, and the reason is substantive")
    log("  rather than numerical, so it is measured here instead of worked around.")
    log("  `n_markets` has SMD +3.31 because treatment is DEFINED as 'active in")
    log("  the target AND in a dead market', which forces n_markets >= 2 for every")
    log("  treated seller. A covariate implied by the treatment definition makes")
    log("  treatment perfectly predictable and destroys overlap. Four covariate")
    log("  sets are tried and the overlap of each is reported.")
    log("")

    ti = np.where(cov["treat"].to_numpy() == 1)[0]
    ci = np.where(cov["treat"].to_numpy() == 0)[0]

    COV_SETS = [
        ("A full (as pre-registered)", COVS),
        ("B minus definitional n_markets",
         [c for c in COVS if c != "n_markets"]),
        ("C Apollon activity + quality",
         ["base_ap", "pos_share", "neg_share", "mean_price", "n_weeks_active",
          "span_days"]),
        ("D baseline size + quality only",
         ["base_ap", "pos_share", "neg_share", "mean_price"]),
    ]

    log("  %-30s %8s %8s %8s %8s %8s" %
        ("covariate set", "n_cov", "max|b|", "overlap", "pairs", "worstSMD"))
    best = None
    trials = {}
    for name, cs in COV_SETS:
        X = cov[cs].to_numpy(float)
        mu, sd = X.mean(0), X.std(0)
        sd[sd == 0] = 1.0
        Xs = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
        bb = logit_fit(Xs, cov["treat"].to_numpy(float))
        lp = Xs @ bb
        # overlap: share of treated whose score lies inside the control range
        lo_c, hi_c = lp[ci].min(), lp[ci].max()
        ov = float(((lp[ti] >= lo_c) & (lp[ti] <= hi_c)).mean())
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
        wb = max(abs(smd(cov.loc[cov["treat"] == 1, c].to_numpy(float),
                         cov.loc[cov["treat"] == 0, c].to_numpy(float)))
                 for c in cs)
        log("  %-30s %8d %8.2f %8.3f %8d %8.3f"
            % (name, len(cs), float(np.max(np.abs(bb[1:]))), ov, len(prs), wb))
        trials[name] = {"n_cov": len(cs), "max_abs_coef":
                        float(np.max(np.abs(bb[1:]))), "overlap": ov,
                        "pairs": len(prs), "worst_smd_before": wb}
        if best is None or len(prs) > len(best[2]):
            best = (name, cs, prs, lp)
    R["psm_trials"] = trials

    name, cs, pairs, lp = best
    log("")
    log("  ★ best set: %s -> %d pairs (%.1f%% of %d treated)"
        % (name, len(pairs), 100.0 * len(pairs) / max(len(ti), 1), len(ti)))
    mt = [p[0] for p in pairs]
    mc = [p[1] for p in pairs]
    worst_before = worst_after = float("nan")
    if pairs:
        log("")
        log("  balance AFTER matching:")
        log("  %-16s %10s %10s %9s %9s"
            % ("covariate", "control", "treated", "SMD", "SMD_before"))
        worst_before = worst_after = 0.0
        for c in cs:
            t = cov.iloc[mt][c].to_numpy(float)
            k = cov.iloc[mc][c].to_numpy(float)
            sb = smd(cov.loc[cov["treat"] == 1, c].to_numpy(float),
                     cov.loc[cov["treat"] == 0, c].to_numpy(float))
            sa = smd(t, k)
            worst_before = max(worst_before, abs(sb))
            worst_after = max(worst_after, abs(sa))
            log("  %-16s %10.4f %10.4f %+9.4f %+9.4f"
                % (c, k.mean(), t.mean(), sa, sb))
        log("")
        log("  worst |SMD|: before %.4f -> after %.4f  %s"
            % (worst_before, worst_after,
               "(imbalance reduced)" if worst_after < worst_before
               else "★ (NOT reduced)"))
    else:
        log("  ★ NO covariate set yields ANY matched pair. The arms do not")
        log("    overlap on observables, so a propensity-matched counterfactual")
        log("    cannot be built here. This is a positivity failure and it is")
        log("    reported as a finding, not repaired by weakening the caliper.")
    R["psm"] = {"set": name, "pairs": len(pairs),
                "worst_smd_before": worst_before, "worst_smd_after": worst_after}

    # ---------------------------------------------------------------- panels
    def build(sel):
        aggp = (ap[ap["vendor"].isin(set(sel))]
                .groupby(["vendor", "week"]).size().rename("y").reset_index())
        full = pd.MultiIndex.from_product([sorted(sel), weeks],
                                          names=["vendor", "week"])
        p = (aggp.set_index(["vendor", "week"]).reindex(full)
             .fillna({"y": 0}).reset_index())
        p = p.rename(columns={"vendor": "seller"}).merge(
            cov[["treat", "stratum", "n_other", "base_ap", "total_rev"]],
            left_on="seller", right_index=True, how="left")
        p["post"] = (p["week"] >= EVENT).astype(int)
        p["did"] = p["treat"] * p["post"]
        p["sw"] = p["stratum"].astype(str) + "|" + p["week"].astype(str)
        return p

    panel_all = build(cand)
    matched_sel = [cov.index[i] for i in mt] + [cov.index[j] for j in mc]
    panel_psm = build(matched_sel) if matched_sel else None

    # moderators, centred; both are PRE-EVENT constants so seller FE absorbs
    # their main effects and only the did-interaction is identified.
    for p in [x for x in (panel_all, panel_psm) if x is not None]:
        dec = p["n_other"].to_numpy(float)
        cen = (p["base_ap"] / p["total_rev"].replace(0, np.nan)).fillna(0.0)
        cen = cen.to_numpy(float)
        p["dec_c"] = (dec - dec.mean()) * p["did"]
        p["cen_c"] = (cen - cen.mean()) * p["did"]
        p["dec0"] = dec
        p["cen0"] = cen

    sep("3. ★ DiD, unmatched vs PSM-matched (same estimator, same FE)")
    log("  %-26s %8s %9s %8s %7s  95%% CI" % ("sample / model", "beta", "se",
                                               "t", "p"))
    res = {}
    for lab, p in (("unmatched", panel_all), ("PSM-matched", panel_psm)):
        if p is None:
            log("  %-26s  (skipped: no matched sample)" % "PSM-matched")
            continue
        for mlab, fes in (("seller+week", ("seller", "week")),
                          ("+stratum x week", ("seller", "week", "sw"))):
            m = fe_did(p, "did", fes=fes)
            if m is None:
                log("  %-26s  (not identified)" % ("%s / %s" % (lab, mlab)))
                continue
            log("  %-26s %+8.4f %9.4f %8.2f %7.4g  [%+.3f, %+.3f]"
                % ("%s / %s" % (lab, mlab), m["beta"], m["se"], m["t"], m["p"],
                   m["lo"], m["hi"]))
            res["%s|%s" % (lab, mlab)] = m
    pm_all = panel_all.loc[(panel_all["post"] == 0) & (panel_all["treat"] == 1),
                           "y"].mean()
    log("")
    log("  treated pre-period mean: %.2f reviews/week (units of the CI above)"
        % pm_all)
    R["did"] = res

    sep("4. ★ H1 and H4 as interactions with the DiD term")
    log("  H1: decentralization (markets active pre, excluding dead + target)")
    log("      predicts MORE recovery -> positive interaction.")
    log("  H4: raw centrality (share of the seller's reviews that were in the")
    log("      target market) predicts NO significant positive relation.")
    log("")
    log("  %-14s %-12s %9s %9s %8s %8s" % ("sample", "term", "beta", "se", "t", "p"))
    mod = {}
    for lab, p in (("unmatched", panel_all), ("PSM-matched", panel_psm)):
        if p is None:
            continue
        for term, name in (("dec_c", "did x decentralization"),
                           ("cen_c", "did x centrality")):
            m = fe_did(p, term, fes=("seller", "week", "sw"))
            if m is None:
                continue
            log("  %-14s %-12s %+9.4f %9.4f %8.2f %8.4g"
                % (lab, term, m["beta"], m["se"], m["t"], m["p"]))
            mod["%s|%s" % (lab, term)] = m
    log("")
    for term, name in (("dec_c", "H1 decentralization"),
                       ("cen_c", "H4 centrality")):
        m = mod.get("PSM-matched|%s" % term)
        if not m:
            continue
        verdict = ("supports a positive moderator" if m["beta"] > 0 and m["p"] < .05
                   else "no significant positive relation")
        R["mod_%s" % term] = m
        log("  %-22s PSM-matched beta=%+.4f p=%.4g  -> %s"
            % (name, m["beta"], m["p"], verdict))

    sep("5. ★ %d placebo event dates (E1 v3 ran 3)" % N_PLACEBO)
    log("  Pre-period data only. A fake event is drawn, the same model is")
    log("  re-estimated on a panel re-cut at that date, and the resulting betas")
    log("  form the null. The real post-period beta is then placed in that null.")
    pre_only = d[(d["ts"] >= PRE0) & (d["ts"] < EVENT)]
    lo_w = PRE0 + pd.Timedelta(weeks=4)
    hi_w = EVENT - pd.Timedelta(weeks=1)
    span = (hi_w - lo_w).days
    rng = np.random.default_rng(20260924)
    null = []
    idx = 0
    while len(null) < N_PLACEBO and idx < N_PLACEBO * 20:
        idx += 1
        fd = lo_w + pd.Timedelta(days=int(rng.integers(0, max(span, 1))))
        fw = pd.date_range(PRE0, EVENT - pd.Timedelta(days=1), freq="W-MON")
        if fd >= fw[-1] or fd <= fw[0]:
            continue
        fpre = pre_only[(pre_only["ts"] >= PRE0) & (pre_only["ts"] < fd)]
        cand_f = sorted(set(fpre.loc[fpre["market"] == TARGET, "vendor"]))
        if len(cand_f) < 20:
            continue
        dead_f = set(fpre.loc[fpre["market"].isin(DEAD), "vendor"])
        apf = pre_only[pre_only["market"] == TARGET]
        aggp = (apf[apf["vendor"].isin(set(cand_f))]
                .groupby(["vendor", "week"]).size().rename("y").reset_index())
        full = pd.MultiIndex.from_product([cand_f, fw], names=["vendor", "week"])
        pf = (aggp.set_index(["vendor", "week"]).reindex(full)
              .fillna({"y": 0}).reset_index().rename(columns={"vendor": "seller"}))
        pf["treat"] = pf["seller"].isin(dead_f).astype(int)
        pf["post"] = (pf["week"] >= fd).astype(int)
        pf["did"] = pf["treat"] * pf["post"]
        m = fe_did(pf, "did", fes=("seller", "week"))
        if m is not None and np.isfinite(m["beta"]):
            null.append(float(m["beta"]))
    null = np.array(null)
    real = res.get("unmatched|seller+week", {}).get("beta", np.nan)
    if len(null) > 10:
        q = np.percentile(null, [2.5, 50, 97.5])
        pk = float((null >= real).mean())
        log("")
        log("  placebos estimated : %d" % len(null))
        log("  null beta: mean %+.4f  sd %.4f  2.5%% %+.4f  median %+.4f  97.5%% %+.4f"
            % (null.mean(), null.std(), q[0], q[1], q[2]))
        log("  real beta (unmatched, seller+week): %+.4f" % real)
        log("  ★ share of placebos >= real: %.4f  (p_placebo)" % pk)
        log("  ★ real beta sits at percentile %.1f of the null"
            % (100.0 * (null < real).mean()))
        R["placebo"] = {"n": int(len(null)), "mean": float(null.mean()),
                        "sd": float(null.std()), "p2.5": float(q[0]),
                        "median": float(q[1]), "p97.5": float(q[2]),
                        "real_beta": float(real), "p_placebo": pk,
                        "percentile": float(100.0 * (null < real).mean())}

    sep("6. Hypotheses NOT run, and why (recorded, not dropped)")
    log("  H2 cross-layer bridging: substrate MEASURED ABSENT (report 08 §1).")
    log("     124 checksum-valid BTC addresses in the social layer; 3 intersect")
    log("     Elliptic++ (822,942); all 3 adjudicated non-transactional (leaked-")
    log("     dump preview, charity donation, one mis-filed cell); none illicit.")
    log("     A positive control recovered an injected address, so the small")
    log("     number is a property of the data, not of the code.")
    log("  H3 functional redundancy: the kilos panel has NO category column and")
    log("     C-45 records that the one available proxy REFUTES the hypothesis.")
    log("     Not run rather than run on a proxy known to point the wrong way.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "38_E3_mechanism.json"), "w",
              encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "38_E3_mechanism.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/38_E3_mechanism.{txt,json}" % RESULTS)
    log("E3_DONE")


if __name__ == "__main__":
    main()
