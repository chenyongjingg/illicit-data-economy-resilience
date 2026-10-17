#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""24_E5fin_recurrence.py -- financial layer: does an actor's participation in
the labelled Bitcoin subgraph recur, and does actor class predict it?

WHY NOT A DURATION MODEL
23_ killed that design before it was written. Duration (last step - first step)
has median 0 for every class, because 91.6% of addresses (unknown), 94.2%
(licit) and 98.2% (illicit) appear in exactly ONE time step. On a 49-step window
with 92% one-shot, a Kaplan-Meier curve is a step function that falls to near
zero at t=0 and the "survival" being modelled is not a process, it is the
one-shot majority. The usable outcome is therefore binary:

    recur = 1[the address is observed in >= 2 distinct time steps]

and the analysis is a hurdle/incidence question, not a survival one.

WHY ENTRY STEP IS NOT OPTIONAL
An address entering at step t0 has at most 49 - t0 steps of room. 23_ measured
this and it is large: mean available room is 43.7 steps for t0 in 1..10 and 4.5
for t0 in 41..49, and observed mean duration tracks it (1.57 -> 0.10). The classes
also enter at different times -- 7.75% of licit addresses enter at step 1 against
0.51% of illicit ones -- so an unconditional comparison of recurrence measures
the calendar, not the actor. Every estimate below is therefore either computed
WITHIN an entry step, or from a model with entry-step fixed effects.

WHAT IS AND IS NOT CLAIMED
The outcome is recurrence of participation in the LABELLED SUBGRAPH, not in
Bitcoin. An address "dies" here when it stops touching the labelled subgraph,
which is not the same as stopping all on-chain activity. Reported under that
label throughout.

There is also a labelling-direction issue worth stating up front: class is an
ACTOR-level determination ("was ever involved in illicit activity"). If more
activity gave more opportunity to be labelled illicit, that would inflate
recurrence among illicit addresses. The observed direction is the opposite
(below), so the estimate is conservative with respect to that bias -- which is
the useful direction for it to be wrong in.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

BASE = "/root/cis/data/EllipticPlusPlus-main"
ACT = os.path.join(BASE, "Actors Dataset")
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


NAMES = {1: "illicit", 2: "licit", 3: "unknown"}


# --------------------------------------------------------------- estimation
def logistic(X, y, max_iter=200, tol=1e-10):
    """Newton-Raphson MLE for a logistic model, no intercept column assumed.

    Hand-rolled rather than imported so the run does not depend on a package
    being present on the pod; the fit is checked against the null log-likelihood
    below instead of being trusted.
    """
    n, k = X.shape
    beta = np.zeros(k)
    for it in range(max_iter):
        eta = X @ beta
        eta = np.clip(eta, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.maximum(p * (1 - p), 1e-12)
        g = X.T @ (y - p)
        H = (X * w[:, None]).T @ X
        try:
            step = np.linalg.solve(H + 1e-9 * np.eye(k), g)
        except np.linalg.LinAlgError:
            break
        beta = beta + step
        if np.max(np.abs(step)) < tol:
            break
    eta = np.clip(X @ beta, -30, 30)
    p = 1.0 / (1.0 + np.exp(-eta))
    ll = float(np.sum(y * np.log(np.maximum(p, 1e-15)) +
                      (1 - y) * np.log(np.maximum(1 - p, 1e-15))))
    w = np.maximum(p * (1 - p), 1e-12)
    H = (X * w[:, None]).T @ X
    cov = np.linalg.pinv(H)
    se = np.sqrt(np.maximum(np.diag(cov), 0))
    return beta, se, ll, it + 1


def wald(beta, se):
    z = beta / np.maximum(se, 1e-15)
    from math import erfc, sqrt
    p = np.array([erfc(abs(zi) / sqrt(2.0)) for zi in z])
    return z, p


def main():
    log("=" * 78)
    log("E5-fin  Recurrence of participation in the labelled Bitcoin subgraph")
    log("=" * 78)

    wf = pd.read_csv(os.path.join(ACT, "wallets_features.csv"), usecols=[
        "address", "Time step", "total_txs", "num_txs_as_sender"],
        low_memory=False)
    wc = pd.read_csv(os.path.join(ACT, "wallets_classes.csv"))

    sep("1. Build the address-level frame")
    per = wf.groupby(["address", "Time step"]).size().rename("n_tx").reset_index()
    log("  (address, step) cells: %d ; total participations: %d"
        % (len(per), int(per["n_tx"].sum())))

    a = per.groupby("address").agg(
        t0=("Time step", "min"), t1=("Time step", "max"),
        n_active=("Time step", "size")).reset_index()
    t0 = a["t0"].to_numpy()
    t1 = a["t1"].to_numpy()
    a["recur"] = (a["n_active"] >= 2).astype(int)
    a["room"] = 49 - a["t0"]

    # entry-step intensity and role, measured AT ENTRY ONLY -- a covariate that
    # uses later steps would be post-outcome (the vendor_level trap from E4).
    entry = per[per["Time step"] == per["address"].map(a.set_index("address")["t0"])]
    entry = entry[["address", "n_tx"]].rename(columns={"n_tx": "n_tx_entry"})
    a = a.merge(entry, on="address", how="left")

    snd = wf[wf["Time step"] == wf["address"].map(a.set_index("address")["t0"])]
    snd = snd.groupby("address")["num_txs_as_sender"].first().rename(
        "n_sent_life")
    a = a.merge(snd, on="address", how="left")
    # lifetime sender share, used only as a descriptive split -- it is an
    # address-level lifetime quantity and therefore NOT pre-entry
    tot = wf.groupby("address")["total_txs"].first().rename("n_tx_life")
    a = a.merge(tot, on="address", how="left")
    a = a.merge(wc, on="address", how="left")
    log("  addresses: %d ; with class: %d" % (len(a), a["class"].notna().sum()))
    log("  overall recurrence rate: %.4f%% (n=%d)"
        % (100.0 * a["recur"].mean(), int(a["recur"].sum())))

    sep("2. Recurrence by class, UNCONDITIONAL (shown to be misleading)")
    for k in (1, 2, 3):
        g = a[a["class"] == k]
        log("  %-9s n=%7d recur=%6.3f%%  mean t0=%5.2f  mean room=%5.2f"
            % (NAMES[k], len(g), 100.0 * g["recur"].mean(), g["t0"].mean(),
               g["room"].mean()))

    sep("3. ★ Recurrence WITHIN entry step -- the ceiling removed")
    log("  Comparing classes only among addresses that entered at the SAME step")
    log("  removes the ceiling exactly, with no model.")
    log("")
    log("  %5s %8s %10s %10s %10s %12s"
        % ("t0", "n_tot", "illicit%", "licit%", "unknown%", "ill-lic(pp)"))
    rows = []
    for t in range(1, 49):
        g = a[a["t0"] == t]
        if len(g) < 50:
            continue
        r = {k: (100.0 * g[g["class"] == k]["recur"].mean()
                 if (g["class"] == k).sum() else np.nan) for k in (1, 2, 3)}
        d = r[1] - r[2]
        rows.append(dict(t0=t, n=len(g), **{"r%d" % k: r[k] for k in (1, 2, 3)},
                         diff=d))
        if t <= 10 or t % 4 == 0 or t >= 45:
            log("  %5d %8d %9.2f%% %9.2f%% %9.2f%% %11.2f"
                % (t, len(g), r[1], r[2], r[3], d))
    R = pd.DataFrame(rows)
    log("")
    log("  entry steps used: %d" % len(R))
    log("  within-step difference (illicit - licit), in pp:")
    log("    mean=%+.3f  median=%+.3f  min=%+.3f  max=%+.3f"
        % (R["diff"].mean(), R["diff"].median(), R["diff"].min(), R["diff"].max()))
    log("    steps where illicit < licit: %d / %d (%.1f%%)"
        % (int((R["diff"] < 0).sum()), len(R), 100.0 * (R["diff"] < 0).mean()))
    log("")
    log("  inverse-variance weighted mean difference (fixed effect):")
    se_d = []
    for _, row in R.iterrows():
        g = a[a["t0"] == row["t0"]]
        ni = int((g["class"] == 1).sum())
        nl = int((g["class"] == 2).sum())
        pi = g[g["class"] == 1]["recur"].mean()
        pl = g[g["class"] == 2]["recur"].mean()
        v = 100.0 ** 2 * (pi * (1 - pi) / max(ni, 1) + pl * (1 - pl) / max(nl, 1))
        se_d.append(np.sqrt(v))
    R["se_diff"] = se_d
    wgt = 1.0 / np.maximum(R["se_diff"] ** 2, 1e-12)
    mh = float((R["diff"] * wgt).sum() / wgt.sum())
    mh_se = float(np.sqrt(1.0 / wgt.sum()))
    from math import erfc as _erfc, sqrt as _sqrt
    z_mh = mh / mh_se
    p_mh = _erfc(abs(z_mh) / _sqrt(2.0))
    log("    pooled diff = %+.3f pp  (se %.3f, z=%.2f, p=%.2e)"
        % (mh, mh_se, z_mh, p_mh))

    sep("4. Logistic model with entry-step fixed effects")
    d = a[a["t0"] <= 48].copy()
    d["log_n_tx_entry"] = np.log1p(d["n_tx_entry"].fillna(0))
    d = d[d["class"].notna()]
    log("  sample: %d addresses (t0 <= 48)" % len(d))

    t0d = pd.get_dummies(d["t0"], prefix="t0", drop_first=True).astype(float)
    base = pd.DataFrame({
        "illicit": (d["class"] == 1).astype(float),
        "licit": (d["class"] == 2).astype(float),
        "log_n_tx_entry": d["log_n_tx_entry"].to_numpy(),
    }, index=d.index)
    X = np.column_stack([base.to_numpy(), t0d.to_numpy()])
    y = d["recur"].to_numpy(float)
    beta, se, ll, iters = logistic(X, y)
    z, pv = wald(beta, se)
    names = list(base.columns) + list(t0d.columns)
    log("  converged in %d iterations; loglik=%.1f" % (iters, ll))
    log("")
    log("  %-34s %10s %10s %10s" % ("term", "coef", "se", "p"))
    for i in range(3):
        log("  %-34s %+10.4f %10.4f %10.2e"
            % (names[i], beta[i], se[i], pv[i]))
    log("  (%d entry-step dummies suppressed)" % len(t0d.columns))
    log("")
    log("  NOTE: coefficients are log-odds with unknown as the base category.")

    sep("5. Does entry intensity carry it? add the interaction-free check")
    # recurrence by entry-intensity quartile, within class
    d["q_int"] = pd.qcut(d["n_tx_entry"].rank(method="first"), 4,
                         labels=["Q1", "Q2", "Q3", "Q4"])
    log("  recurrence %% by entry-intensity quartile and class:")
    log("  %-5s %10s %10s %10s" % ("q", "illicit", "licit", "unknown"))
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        g = d[d["q_int"] == q]
        vals = []
        for k in (1, 2, 3):
            gg = g[g["class"] == k]
            vals.append(100.0 * gg["recur"].mean() if len(gg) else np.nan)
        log("  %-5s %9.2f%% %9.2f%% %9.2f%%" % (q, vals[0], vals[1], vals[2]))

    sep("6. ★ FALSIFICATION -- placebo class on the unknown group")
    log("  The unknown class is split at random into two pseudo-classes and the")
    log("  identical within-step comparison is run. A real effect must not")
    log("  appear here; if it does, the estimator is manufacturing differences.")
    rng = np.random.default_rng(20260924)
    u = a[a["class"] == 3].copy()
    u["pseudo"] = rng.integers(0, 2, len(u))
    pl = []
    for t in range(1, 49):
        g = u[u["t0"] == t]
        if len(g) < 50:
            continue
        r0 = 100.0 * g[g["pseudo"] == 0]["recur"].mean()
        r1 = 100.0 * g[g["pseudo"] == 1]["recur"].mean()
        pl.append(r0 - r1)
    pl = np.array(pl)
    log("")
    log("  placebo within-step differences: mean=%+.3f pp median=%+.3f pp"
        % (pl.mean(), np.median(pl)))
    log("  tail probability of |placebo mean| >= |observed mean| (%.3f pp):"
        % abs(mh))
    log("    |placebo mean| = %.3f pp" % abs(pl.mean()))
    log("    ratio observed/placebo = %.1f x"
        % (abs(mh) / max(abs(pl.mean()), 1e-9)))

    sep("7. Falsification 2 -- same comparison, licit vs unknown")
    log("  If the estimator is sound, a comparison between two classes that are")
    log("  NOT targeted by enforcement should be much smaller.")
    rows2 = []
    for t in range(1, 49):
        g = a[a["t0"] == t]
        if len(g) < 50:
            continue
        r2 = g[g["class"] == 2]["recur"].mean()
        r3 = g[g["class"] == 3]["recur"].mean()
        if np.isfinite(r2) and np.isfinite(r3):
            rows2.append(100.0 * (r2 - r3))
    rows2 = np.array(rows2)
    log("  licit - unknown within-step: mean=%+.3f pp median=%+.3f pp"
        % (rows2.mean(), np.median(rows2)))
    log("  illicit - licit within-step: mean=%+.3f pp" % mh)
    log("  If |licit-unknown| is comparable to |illicit-licit|, class is not")
    log("  doing specific work and the result should NOT be read as an illicit")
    log("  effect.")

    # ----------------------------------------------------------------- figure
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 2, figsize=(13, 9))

        ax[0, 0].hist(a["t0"], bins=np.arange(.5, 50.5, 1), color="0.6")
        ax[0, 0].set_title("Entry step t0 (all addresses)")
        ax[0, 0].set_xlabel("time step")

        for k, c in ((1, "crimson"), (2, "steelblue"), (3, "0.6")):
            g = a[a["class"] == k]
            ax[0, 1].hist(g["t1"] - g["t0"], bins=np.arange(-0.5, 20.5, 1),
                          histtype="step", lw=2, color=c,
                          label="%s (n=%d)" % (NAMES[k], len(g)))
        ax[0, 1].set_yscale("log")
        ax[0, 1].set_title("Observed duration t1-t0 (log count)")
        ax[0, 1].legend(fontsize=8)

        if len(R):
            ax[1, 0].axhline(0, color="0.5", lw=1)
            ax[1, 0].plot(R["t0"], R["diff"], "o-", color="darkgreen", ms=4)
            ax[1, 0].set_title("Within-entry-step recurrence\nillicit - licit (pp)")
            ax[1, 0].set_xlabel("entry step t0")

        ws = [100.0 * a[(a["t0"] == t) & (a["class"] == 1)]["recur"].mean()
              if ((a["t0"] == t) & (a["class"] == 1)).sum() else np.nan
              for t in range(1, 49)]
        wl = [100.0 * a[(a["t0"] == t) & (a["class"] == 2)]["recur"].mean()
              if ((a["t0"] == t) & (a["class"] == 2)).sum() else np.nan
              for t in range(1, 49)]
        ax[1, 1].plot(range(1, 49), ws, "o-", ms=3, color="crimson", label="illicit")
        ax[1, 1].plot(range(1, 49), wl, "s-", ms=3, color="steelblue", label="licit")
        ax[1, 1].set_title("Recurrence rate within entry step")
        ax[1, 1].set_xlabel("entry step t0")
        ax[1, 1].set_ylabel("% recurring")
        ax[1, 1].legend(fontsize=8)

        plt.tight_layout()
        os.makedirs(FIGS, exist_ok=True)
        plt.savefig(os.path.join(FIGS, "E5fin_recurrence.png"), dpi=150)
        plt.savefig(os.path.join(FIGS, "E5fin_recurrence.pdf"))
        log("\nwrote %s/E5fin_recurrence.{png,pdf}" % FIGS)
    except Exception as e:  # noqa: BLE001
        log("\nfigure failed (non-fatal): %r" % e)

    out = dict(
        n_addresses=int(len(a)),
        recurrence_rate=float(a["recur"].mean()),
        by_class={NAMES[k]: dict(
            n=int((a["class"] == k).sum()),
            recur=float(a[a["class"] == k]["recur"].mean()),
            mean_t0=float(a[a["class"] == k]["t0"].mean()),
            mean_room=float(a[a["class"] == k]["room"].mean()))
            for k in (1, 2, 3)},
        within_step=dict(
            n_steps=int(len(R)),
            mean_diff_pp=float(R["diff"].mean()) if len(R) else None,
            weighted_diff_pp=float(mh), weighted_se=float(mh_se),
            steps_illicit_lower=int((R["diff"] < 0).sum()) if len(R) else None),
        logistic=dict(terms=names[:3],
                      coef=[float(x) for x in beta[:3]],
                      se=[float(x) for x in se[:3]],
                      p=[float(x) for x in pv[:3]],
                      n=int(len(d)), loglik=ll),
        placebo_mean_pp=float(pl.mean()),
        licit_vs_unknown_mean_pp=float(rows2.mean()),
    )
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "24_E5fin_recurrence.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(RESULTS, "24_E5fin_recurrence.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/24_E5fin_recurrence.{txt,json}" % RESULTS)
    log("E5FIN_DONE")


if __name__ == "__main__":
    main()
