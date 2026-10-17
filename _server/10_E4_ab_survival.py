#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""10_E4_ab_survival.py -- E4: how long until a darknet listing transacts?

Why this outcome and not the one in the plan
--------------------------------------------
The sprint plan specified vendor-tenure survival. C-26 killed it: AlphaBay's
listing table carries no vendor identifier, and vendor names are not recoverable
from text (only 8.9% of headings end in a parenthetical, and the commonest are
`WARRANTY`, `FREE SHIPPING`, `ESCROW` -- marketing phrases).

The table does carry `tenure_days` and `censored`, which looks like a ready-made
survival frame. It is not. `censored` is True for **all 114,231 rows**: there are
ZERO events, and `tenure_days` is only the age of a listing at the scrape date --
a backward recurrence time, length-biased by construction, from which no hazard
can be estimated.

`09_validate_ab_linkage.py` established the outcome that IS identifiable:
**time from listing to the item's first feedback event**, which `ab_feedback`
timestamps. The linkage was verified before use, not assumed:

  * `n_feedback` equals the feedback row count for all 52,494 linked items
    ((n_feedback==0) XOR (no rows) = 0);
  * zero feedback events precede their own listing date;
  * `item_number` is unique in the items file (114,231 distinct).

Exclusions, all counted and reported in the run:
  * 1 header row leaked into the feedback stream (`rating == 'rating'`, ts NaT);
  * 57 feedback rows timestamped AFTER the dump date -- consistent with none of
    the rest of the file, so they are dropped rather than silently kept.

Post-outcome variables are excluded by construction. `n_feedback`, `avg_feedback`
and `sold` all measure what happened after listing; using them to predict time to
first transaction would be circular. `vendor_level` and `trust_level` are the
harder case: they are plausibly scrape-time values. They are reported in a
separate, clearly-flagged model so the reader can see how much they move things.

Output: results/10_E4_ab_survival.{txt,json}, results/figs/E4_ab_survival.{png,pdf}
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import traceback

import numpy as np
import pandas as pd

WORK = "/root/cis/work"
RESULTS = "/root/cis/results"
FIGS = os.path.join(RESULTS, "figs")
SCRAPE = pd.Timestamp("2017-01-28")
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


def km_curve(dur, ev, max_t=None):
    d = np.asarray(dur, dtype=float)
    e = np.asarray(ev, dtype=bool)
    o = np.argsort(d)
    d, e = d[o], e[o]
    n, at, i, S = len(d), len(d), 0, 1.0
    ts, ss = [0.0], [1.0]
    while i < n:
        t, j = d[i], i
        if max_t is not None and t > max_t:
            break
        while j < n and d[j] == t:
            j += 1
        k = int(e[i:j].sum())
        if k:
            S *= (1 - k / at)
            ts.append(float(t))
            ss.append(S)
        at -= (j - i)
        i = j
    return np.asarray(ts), np.asarray(ss)


def km_summary(dur, ev, label, cps=(1, 3, 7, 14, 30, 60, 90, 180)):
    out = {"label": label, "n": int(len(dur)), "events": int(np.sum(ev))}
    try:
        from lifelines import KaplanMeierFitter
        k = KaplanMeierFitter()
        k.fit(dur, event_observed=ev)
        for t in cps:
            out["S_%g" % t] = float(np.asarray(k.predict(t)).reshape(-1)[0])
        out["median"] = float(k.median_survival_time_)
        out["estimator"] = "lifelines"
    except Exception:  # noqa: BLE001
        log("  !! lifelines failed for %r:" % label)
        for ln in traceback.format_exc().splitlines():
            log("     " + ln)
        ts, ss = km_curve(dur, ev)
        for t in cps:
            out["S_%g" % t] = float(ss[max(int(np.searchsorted(ts, t, "right")) - 1, 0)])
        out["median"] = float(ts[np.argmax(ss <= 0.5)]) if (ss <= 0.5).any() else np.inf
        out["estimator"] = "manual product-limit"
    return out


def logrank(g, dur, ev, name):
    if pd.Series(g).nunique() < 2:
        log("  log-rank (%s): not defined" % name)
        return None
    try:
        from lifelines.statistics import multivariate_logrank_test
        r = multivariate_logrank_test(dur, g, ev)
        log("  log-rank (%s): chi2=%.1f dof=%d p=%.3g"
            % (name, r.test_statistic, r.degrees_of_freedom, r.p_value))
        return {"chi2": float(r.test_statistic), "dof": int(r.degrees_of_freedom),
                "p": float(r.p_value)}
    except Exception:  # noqa: BLE001
        log("  !! log-rank (%s): %s" % (name, traceback.format_exc().splitlines()[-1]))
        return None


def main():
    t0 = dt.datetime.now()
    log("=" * 78)
    log("E4 -- ALPHABAY LISTING TIME-TO-FIRST-TRANSACTION  %s"
        % t0.isoformat(timespec="seconds"))
    log("=" * 78)
    R["run_at"] = t0.isoformat(timespec="seconds")

    items = pd.read_parquet(os.path.join(WORK, "ab_items.parquet"))
    fb = pd.read_parquet(os.path.join(WORK, "ab_feedback.parquet"))

    sep("1. Exclusions, counted")
    n0 = len(fb)
    fb = fb[fb["ts"].notna() & fb["item_number"].notna()].copy()
    n_leak = n0 - len(fb)
    fb["item_number"] = fb["item_number"].astype("int64")
    n_after = int((fb["ts"] > SCRAPE).sum())
    fb = fb[fb["ts"] <= SCRAPE].copy()
    log("  feedback rows: %d" % n0)
    log("    dropped, leaked header row (ts NaT):            %d" % n_leak)
    log("    dropped, timestamped after the dump (%s): %d" % (SCRAPE.date(), n_after))
    log("    retained:                                       %d" % len(fb))
    log("")
    log("  NOTE on the %d post-dump rows: they are not a rounding error to bury."
        % n_after)
    log("  A file dated %s containing later timestamps is internally inconsistent,"
        % SCRAPE.date())
    log("  and the dump date is also the censoring date, so they are excluded.")
    R["exclusions"] = {"feedback_rows_in": int(n0), "leaked_header": int(n_leak),
                       "after_dump": int(n_after), "retained": int(len(fb))}

    first = fb.groupby("item_number")["ts"].min().rename("first_fb")
    d = items.merge(first, left_on="item_number", right_index=True, how="left")
    d["event"] = d["first_fb"].notna()
    d["duration"] = np.where(
        d["event"],
        (d["first_fb"] - d["listed_date"]).dt.total_seconds() / 86400.0,
        (SCRAPE - d["listed_date"]).dt.total_seconds() / 86400.0).astype(float)
    bad = d["duration"].isna() | (d["duration"] < 0)
    log("")
    log("  listing frame: n=%d ; dropped for missing/negative duration: %d"
        % (len(d), int(bad.sum())))
    d = d[~bad].copy()
    log("  events (>=1 feedback): %d (%.1f%%) ; censored at %s: %d"
        % (int(d["event"].sum()), 100.0 * d["event"].mean(), SCRAPE.date(),
           int((~d["event"]).sum())))
    log("  listings span %s .. %s" % (d["listed_date"].min().date(),
                                      d["listed_date"].max().date()))
    R["frame"] = {"n": int(len(d)), "events": int(d["event"].sum()),
                  "censored": int((~d["event"]).sum()),
                  "event_rate": round(float(d["event"].mean()), 4),
                  "listed_min": str(d["listed_date"].min().date()),
                  "listed_max": str(d["listed_date"].max().date())}
    log("")
    log("  WHAT THIS OUTCOME IS: time from listing to the FIRST transaction. It is")
    log("  a measure of how fast a listing becomes economically active, not of")
    log("  takedown resistance. Event = first feedback; cessation of the listing")
    log("  itself is never observed, because the dump censors every item at once.")

    # --------------------------------------------------------- 2. overall
    sep("2. Overall: how long until a listing first transacts?")
    s = km_summary(d["duration"].to_numpy(), d["event"].to_numpy(), "all")
    R["overall"] = {k: v for k, v in s.items()}
    log("  estimator: %s" % s["estimator"])
    for t in (1, 3, 7, 14, 30, 60, 90, 180):
        if "S_%g" % t in s:
            log("    S(%3d d) = %.4f" % (t, s["S_%g" % t]))
    log("  median time to first transaction: %.1f days" % s["median"])
    log("  (among listings that ever transacted, the median is %.1f days)"
        % d.loc[d["event"], "duration"].median())
    log("")
    log("  length-bias warning: items enter this frame at their listing date and")
    log("  are censored together at the dump. A listing created long before the")
    log("  dump has had more time to transact, so cohort age is a real covariate")
    log("  and is modelled as one below rather than left in the error term.")

    # ------------------------------------------------------- 3. by group
    sep("3. Which listings transact faster?")
    d["price_log"] = np.log1p(d["price"].clip(lower=0))
    d["qty_log"] = np.log1p(d["quantity"].clip(lower=0))
    d["cohort"] = d["listed_date"].dt.to_period("Q").astype(str)

    for col, lbl, k in (("product_class", "product class", 4),
                        ("category1", "top-level category", 6),
                        ("shipsto", "ships to", 6),
                        ("origin", "origin", 6)):
        top = d[col].astype(str).value_counts().head(k).index.tolist()
        g = np.where(d[col].astype(str).isin(top), d[col].astype(str), "other")
        rows = []
        for gg in top + ["other"]:
            m = g == gg
            if m.sum() < 200:
                continue
            r = km_summary(d.loc[m, "duration"].to_numpy(), d.loc[m, "event"].to_numpy(), gg,
                           cps=(7, 30))
            rows.append({"group": gg[:38], "n": int(m.sum()),
                         "events": int(d.loc[m, "event"].sum()),
                         "median_days": round(r["median"], 1),
                         "S_7d": round(r.get("S_7", np.nan), 3),
                         "S_30d": round(r.get("S_30", np.nan), 3)})
        tdf = pd.DataFrame(rows).sort_values("n", ascending=False)
        log("")
        log("  by %s:" % lbl)
        log(tdf.to_string(index=False))
        lr = logrank(g, d["duration"], d["event"], lbl)
        R["by_" + col] = {"table": tdf.to_dict("records"), "logrank": lr}

    log("")
    log("  by price quartile:")
    d["price_q"] = pd.qcut(d["price"], 4, labels=["Q1 cheap", "Q2", "Q3", "Q4 dear"])
    rows = []
    for g in ["Q1 cheap", "Q2", "Q3", "Q4 dear"]:
        m = d["price_q"].astype(str) == g
        r = km_summary(d.loc[m, "duration"].to_numpy(), d.loc[m, "event"].to_numpy(), g,
                       cps=(7, 30))
        rows.append({"group": g, "n": int(m.sum()), "median_days": round(r["median"], 1),
                     "S_7d": round(r.get("S_7", np.nan), 3),
                     "S_30d": round(r.get("S_30", np.nan), 3)})
    pdf = pd.DataFrame(rows)
    log(pdf.to_string(index=False))
    lr = logrank(d["price_q"].astype(str), d["duration"], d["event"], "price quartile")
    R["by_price_q"] = {"table": pdf.to_dict("records"), "logrank": lr}

    log("")
    log("  by listing quarter (market maturation / cohort age):")
    cq = d["cohort"].value_counts()
    keep = cq[cq >= 300].index.tolist()
    rows = []
    for g in sorted(keep):
        m = d["cohort"] == g
        r = km_summary(d.loc[m, "duration"].to_numpy(), d.loc[m, "event"].to_numpy(), g,
                       cps=(30,))
        rows.append({"quarter": g, "n": int(m.sum()),
                     "median_days": round(r["median"], 1),
                     "S_30d": round(r.get("S_30", np.nan), 3)})
    cdf = pd.DataFrame(rows)
    log(cdf.to_string(index=False))
    lr = logrank(np.where(d["cohort"].isin(keep), d["cohort"], "other"),
                 d["duration"], d["event"], "listing quarter")
    R["by_cohort"] = {"table": cdf.to_dict("records"), "logrank": lr}

    # ------------------------------------------------------------ 4. Cox
    sep("4. Cox models")
    cov_pre = ["price_log", "qty_log", "heading_len", "blurb_len", "n_tags"]
    cov_q = ["vendor_level", "trust_level"]
    dummy_src = []
    for col, k in (("product_class", 2), ("category1", 6), ("shipsto", 6), ("origin", 6)):
        top = d[col].astype(str).value_counts().head(k).index.tolist()
        val = np.where(d[col].astype(str).isin(top), d[col].astype(str), "other")
        dm = pd.get_dummies(val, prefix=col, drop_first=True).astype(float)
        d = pd.concat([d, dm], axis=1)
        dummy_src += list(dm.columns)

    def run(cols, label):
        cols = [c for c in cols if d[c].nunique() > 1]
        f = d[["duration", "event"] + cols].dropna().copy()
        z = f.copy()
        for c in cols:
            sd = float(f[c].std())
            if sd > 0:
                z[c] = (z[c] - f[c].mean()) / sd
        try:
            from lifelines import CoxPHFitter
            from lifelines.statistics import proportional_hazard_test
            m = CoxPHFitter()
            m.fit(z, duration_col="duration", event_col="event")
            log("")
            log("  --- %s ---" % label)
            log("  n=%d events=%d concordance=%.4f"
                % (len(z), int(z["event"].sum()), m.concordance_index_))
            log(m.summary[["exp(coef)", "exp(coef) lower 95%",
                           "exp(coef) upper 95%", "p"]].round(4).to_string())
            ph = proportional_hazard_test(m, z, time_transform="rank")
            phs = {k: float(v) for k, v in ph.summary["p"].items()}
            viol = sorted(k for k, v in phs.items() if v < 0.05)
            log("  PH rank-test violations at p<0.05: %d/%d %s"
                % (len(viol), len(phs), viol[:6]))
            if viol:
                log("  -> the violated coefficients are time-varying; their HRs are")
                log("     TIME-AVERAGED and the KM medians above are the")
                log("     assumption-free evidence.")
            return {"n": int(len(z)), "events": int(z["event"].sum()),
                    "concordance": round(float(m.concordance_index_), 4),
                    "hr_per_sd": {k: round(float(v), 4) for k, v in
                                  m.summary["exp(coef)"].items()},
                    "ci_low": {k: round(float(v), 4) for k, v in
                               m.summary["exp(coef) lower 95%"].items()},
                    "ci_high": {k: round(float(v), 4) for k, v in
                                m.summary["exp(coef) upper 95%"].items()},
                    "p": {k: round(float(v), 6) for k, v in m.summary["p"].items()},
                    "ph_violations": viol}
        except Exception:  # noqa: BLE001
            log("  !! Cox (%s) failed:" % label)
            for ln in traceback.format_exc().splitlines():
                log("     " + ln)
            return None

    cox = {}
    cox["pre_listing_only"] = run(cov_pre + dummy_src,
                                  "PRE-LISTING covariates only (safe)")
    cox["plus_vendor_levels"] = run(cov_pre + dummy_src + cov_q,
                                    "plus vendor_level/trust_level -- FLAGGED: these "
                                    "may be scrape-time,\n     i.e. measured after the "
                                    "outcome, so this model is not causal")
    R["cox"] = cox

    # ------------------------------------------------------------ 5. figure
    sep("5. Figure")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        os.makedirs(FIGS, exist_ok=True)
        fig, ax = plt.subplots(2, 2, figsize=(11.5, 8))
        MAXT = 120

        def step(a, sub, label, m=MAXT):
            t_, s_ = km_curve(sub["duration"], sub["event"], m)
            a.step(t_, s_, where="post", label=label)

        step(ax[0, 0], d, "all listings (n=%d, %d events)" % (len(d), int(d["event"].sum())))
        ax[0, 0].axhline(0.5, ls=":", c="grey", lw=1)
        ax[0, 0].set_title("(a) Time from listing to first transaction")
        ax[0, 0].set_ylabel("S(t) = no transaction yet")
        ax[0, 0].legend(fontsize=8)

        for g in d["product_class"].astype(str).value_counts().head(3).index:
            step(ax[0, 1], d[d["product_class"].astype(str) == g],
                 "%s (n=%d)" % (g, int((d["product_class"].astype(str) == g).sum())))
        ax[0, 1].set_title("(b) By product class")
        ax[0, 1].legend(fontsize=8)

        for g in ["Q1 cheap", "Q2", "Q3", "Q4 dear"]:
            step(ax[1, 0], d[d["price_q"].astype(str) == g], g)
        ax[1, 0].set_title("(c) By price quartile")
        ax[1, 0].set_xlabel("days since listing")
        ax[1, 0].set_ylabel("S(t) = no transaction yet")
        ax[1, 0].legend(fontsize=8)

        for g in sorted(keep)[:8]:
            step(ax[1, 1], d[d["cohort"] == g], "%s (n=%d)" % (g, int((d["cohort"] == g).sum())))
        ax[1, 1].set_title("(d) By listing quarter\n(cohort age differs, so these are not")
        ax[1, 1].set_xlabel("days since listing")
        ax[1, 1].legend(fontsize=7)
        for a_ in ax.ravel():
            a_.grid(alpha=.3)
        fig.suptitle("E4 - AlphaBay listings (n=%d). Event = first feedback; all items "
                     "censored at the 2017-01-28 dump." % len(d), fontsize=10)
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        for ext in ("png", "pdf"):
            fp = os.path.join(FIGS, "E4_ab_survival.%s" % ext)
            fig.savefig(fp, dpi=160)
            log("  wrote %s" % fp)
        plt.close(fig)
    except Exception:  # noqa: BLE001
        log("  !! figure failed:")
        for ln in traceback.format_exc().splitlines():
            log("     " + ln)

    sep("6. VERDICT")
    log("  ESTABLISHED:")
    log("    * median time from listing to first transaction: %.1f days (n=%d,"
        % (s["median"], len(d)))
    log("      %.1f%% events). Among listings that ever transacted, %.1f days."
        % (100 * d["event"].mean(), d.loc[d["event"], "duration"].median()))
    log("    * group contrasts are tested above by log-rank and jointly by Cox.")
    log("  NOT ESTABLISHED:")
    log("    * vendor-level anything: AlphaBay has no vendor identifier (C-26).")
    log("    * listing 'survival' in the takedown sense: every item is censored at")
    log("      the same instant, so no listing end is ever observed.")
    log("    * anything about the ecosystem after 2017-01-28.")
    log("    * causal readings of vendor_level/trust_level, which may be measured")
    log("      after the outcome.")
    log("    * the standard errors assume independent listings; with no vendor key,")
    log("      clustering by seller is impossible here and the true SEs are larger.")
    R["limits"] = [
        "no vendor identifier -> unit is the listing; no seller-level clustering possible",
        "all items censored at one instant; listing end never observed",
        "vendor_level/trust_level may be post-outcome",
        "feedback left by only some buyers: first feedback >= first sale",
        "self-report: feedback exists only if a buyer chose to leave it",
    ]

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "10_E4_ab_survival.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    with open(os.path.join(RESULTS, "10_E4_ab_survival.json"), "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, default=str)
    log("\nwrote %s/10_E4_ab_survival.{txt,json}" % RESULTS)
    log("E4_DONE")


if __name__ == "__main__":
    sys.exit(main())
