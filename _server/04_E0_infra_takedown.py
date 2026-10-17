#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""04_E0_infra_takedown.py -- E0: how long does malicious infrastructure survive?

Question (RQ1 at the infrastructure layer). Once a malicious URL is recorded in
a public blocklist, how long does it stay online -- and what about the URL or its
hosting predicts a longer life? "Resilience" here is the survival of the illicit
resource against the takedown process, which is the one place in this project
where an *event time is observed directly* rather than inferred.

Identification (established by 03_iden_infra.py, not assumed here)
------------------------------------------------------------------
abuse.ch retains recent records and drops the rest: 100% of every 2018-2025
cohort is `online`, and `last_online` exists only inside an 89-day window. So the
analysis is restricted to URLs added inside that window (date_added >= window
start), where a takedown occurring after registration would have been recorded.

Four measurement limits are carried into the report rather than smoothed away:

1. `last_online` is the last time the URL was *seen alive*, not the moment it went
   down. The true takedown lies in (last_online, next probe], so every duration
   here is a LOWER BOUND on survival. Detection cadence is not published.
2. Some offline URLs carry NO `last_online` at all -- the takedown is known to
   have happened but its time is not observed. Dropping them removes events, and
   dropping events biases survival upward. They are therefore not dropped
   silently: they are counted, and the median is bracketed by re-running the
   curve with them placed at both extremes of their feasible interval.
3. Co-location is measured inside the same observation window, so "a block with
   many URLs" means many URLs registered during the window, not the block's whole
   history. A sensitivity model uses whole-feed counts instead.
4. `date_added` is when the URL entered this blocklist, not when it was created.

Two features of this feed also constrain the design and are reported as findings
rather than worked around: `threat` holds a SINGLE value in the cohort, and 87%
of URLs are bare IP literals rather than domain names.

Output: results/04_E0_infra_takedown.{txt,json}, results/figs/E0_*.{png,pdf}
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import traceback
from collections import Counter
from urllib.parse import urlsplit

import numpy as np
import pandas as pd

WORK = "/root/cis/work"
RESULTS = "/root/cis/results"
FIGS = os.path.join(RESULTS, "figs")
_L: list[str] = []
R: dict = {}

# Tags URLhaus attaches describe the *payload* (file type, architecture) or the
# *family*. Splitting them is a stated rule, not a guess about any one row: a tag
# in PAYLOAD is a payload descriptor, the first tag outside it is taken as the
# family. Anything unmapped stays "unknown" and is reported as such.
PAYLOAD = {"elf", "exe", "dll", "doc", "docx", "xls", "xlsx", "zip", "rar", "msi",
           "apk", "jar", "js", "vbs", "sh", "ps1", "powershell", "hta", "iso",
           "mips", "arm", "arm64", "sparc", "x86", "x86-64", "32-bit", "64-bit",
           "mips64", "ppc", "m68k", "python", "perl", "lua", "php", "html",
           "payload", "dropper", "loader", "downloader"}
_ARCH = re.compile(r"^(\d+-bit|unknown-arch)$", re.I)


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _L.append(s)


def sep(t):
    log("")
    log("=" * 78)
    log(t)
    log("=" * 78)


# ------------------------------------------------------------------ helpers
def km_summary(dur, ev, label, checkpoints=(0.5, 1, 2, 7, 14, 30, 60, 90)):
    """Fit KM and return the numbers we report, with an honest fallback.

    The fallback is a product-limit estimate evaluated only AT the checkpoints.
    `03_iden_infra.py` printed one line per event time, which turned a summary
    into a 1.5 MB file; a report too large to read is not a report.
    """
    out = {"label": label, "n": int(len(dur)), "events": int(np.sum(ev))}
    try:
        from lifelines import KaplanMeierFitter
        kmf = KaplanMeierFitter()
        kmf.fit(dur, event_observed=ev)
        for t in checkpoints:
            out["S_%g" % t] = float(np.asarray(kmf.predict(t)).reshape(-1)[0])
        out["median"] = float(kmf.median_survival_time_)
        out["estimator"] = "lifelines"
        return out
    except Exception:  # noqa: BLE001
        log("    !! lifelines failed for %r -- real traceback follows:" % label)
        for ln in traceback.format_exc().splitlines():
            log("       " + ln)
        d = np.asarray(dur, dtype=float)
        e = np.asarray(ev, dtype=bool)
        o = np.argsort(d)
        d, e = d[o], e[o]
        n, at_risk, i = len(d), len(d), 0
        S = 1.0
        ts, ss = [0.0], [1.0]
        while i < n:
            t, j = d[i], i
            while j < n and d[j] == t:
                j += 1
            k = int(e[i:j].sum())
            if k:
                S *= (1.0 - k / at_risk)
                ts.append(float(t))
                ss.append(S)
            at_risk -= (j - i)
            i = j
        ts, ss = np.asarray(ts), np.asarray(ss)
        for t in checkpoints:
            out["S_%g" % t] = float(ss[max(int(np.searchsorted(ts, t, "right")) - 1, 0)])
        out["median"] = (float(ts[np.argmax(ss <= 0.5)]) if (ss <= 0.5).any()
                         else float("inf"))
        out["estimator"] = "manual product-limit (lifelines failed)"
        return out


def km_curve(dur, ev, max_t=None):
    """Product-limit as (t, S) step arrays -- used for plotting, not inference."""
    d = np.asarray(dur, dtype=float)
    e = np.asarray(ev, dtype=bool)
    o = np.argsort(d)
    d, e = d[o], e[o]
    n, at_risk, i = len(d), len(d), 0
    S = 1.0
    ts, ss = [0.0], [1.0]
    while i < n:
        t, j = d[i], i
        if max_t is not None and t > max_t:
            break
        while j < n and d[j] == t:
            j += 1
        k = int(e[i:j].sum())
        if k:
            S *= (1.0 - k / at_risk)
            ts.append(float(t))
            ss.append(S)
        at_risk -= (j - i)
        i = j
    return np.asarray(ts), np.asarray(ss)


def logrank(groups, dur, ev, name):
    """Omnibus log-rank; returns None (and says why) when it is not defined."""
    k = pd.Series(groups).nunique()
    if k < 2:
        log("  log-rank: not defined -- only %d group(s)." % k)
        return None
    try:
        from lifelines.statistics import multivariate_logrank_test
        res = multivariate_logrank_test(dur, groups, ev)
        s, p, dfree = (float(res.test_statistic), float(res.p_value),
                       int(res.degrees_of_freedom))
        log("  omnibus log-rank (%s): chi2=%.1f  dof=%d  p=%.3g" % (name, s, dfree, p))
        return {"test_statistic": s, "dof": dfree, "p": p, "k_groups": int(k)}
    except Exception:  # noqa: BLE001
        log("  !! log-rank failed (%s):" % name)
        for ln in traceback.format_exc().splitlines():
            log("     " + ln)
        return None


_IPV4 = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def host_of(u):
    try:
        return (urlsplit(u if "://" in u else "http://" + u).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def infra_block(h):
    """The unit a takedown actually acts on.

    For a bare IP the operator's control point is usually not the single address
    but the /24 it sits in, so the block is the first three octets. For a domain
    it is the registrable host. Mixing the two under one key would merge an IP
    '1.2.3.4' with a domain named '1.2.3.4', so the two namespaces are prefixed.
    """
    if _IPV4.match(h):
        return "ip24:" + ".".join(h.split(".")[:3])
    return "host:" + h


def main():
    t0 = dt.datetime.now()
    log("=" * 78)
    log("E0 -- INFRASTRUCTURE TAKEDOWN LATENCY (URLhaus)  %s"
        % t0.isoformat(timespec="seconds"))
    log("=" * 78)
    R["run_at"] = t0.isoformat(timespec="seconds")

    u = pd.read_parquet(os.path.join(WORK, "ioc_urlhaus.parquet"))
    sep("0. Columns as read")
    log("  %s" % list(u.columns))
    log("  rows: %d" % len(u))

    u["added"] = pd.to_datetime(u["date_added"], errors="coerce")
    u["lo"] = pd.to_datetime(u["last_online"], errors="coerce")
    u["online"] = u["url_status"].str.lower().eq("online")
    W0, T_END = u["lo"].min(), u["lo"].max()

    # ------------------------------------------------------------ 1. cohort
    sep("1. Analysable cohort, censoring, and the rows that cannot be timed")
    coh = u[u["added"] >= W0].copy()
    coh["t_event"] = (coh["lo"] - coh["added"]).dt.total_seconds() / 86400.0
    coh["t_cens"] = (T_END - coh["added"]).dt.total_seconds() / 86400.0
    log("  window %s .. %s  (%.0f days)" % (W0.date(), T_END.date(), (T_END - W0).days))
    log("  rows added inside the window: n=%d (%.1f%% of feed)"
        % (len(coh), 100.0 * len(coh) / len(u)))

    untimed = coh[coh["t_event"].isna() & ~coh["online"]]
    neg = coh[(coh["t_event"] < 0) & ~coh["online"]]
    log("")
    log("  ROWS THAT CANNOT BE TIMED -- reported, not silently dropped:")
    log("    offline with NO last_online (takedown known, time unobserved): %d"
        % len(untimed))
    log("    offline with last_online BEFORE date_added (inconsistent):     %d" % len(neg))
    log("    share of the cohort affected: %.1f%%"
        % (100.0 * (len(untimed) + len(neg)) / len(coh)))
    log("    These are EVENTS whose time we do not know. Dropping them removes")
    log("    events, which biases survival UP. Their feasible interval is")
    log("    [0, t_cens], so section 2 brackets the median with them placed at")
    log("    both ends of it.")
    R["untimed"] = {"no_last_online": int(len(untimed)), "negative": int(len(neg)),
                    "pct_of_cohort": round(100.0 * (len(untimed) + len(neg)) / len(coh), 2)}

    coh = coh[coh["t_event"].notna() & (coh["t_event"] >= 0)].copy()
    coh["duration"] = np.where(coh["online"].to_numpy(),
                               coh["t_cens"].to_numpy(), coh["t_event"].to_numpy())
    coh["event"] = ~coh["online"]
    log("")
    log("  timing-analysable cohort n=%d  events=%d  censored=%d  event rate=%.1f%%"
        % (len(coh), int(coh["event"].sum()), int((~coh["event"]).sum()),
           100.0 * coh["event"].mean()))
    R["cohort"] = {"n": int(len(coh)), "events": int(coh["event"].sum()),
                   "censored": int((~coh["event"]).sum()),
                   "event_rate": round(float(coh["event"].mean()), 4),
                   "window_start": str(W0.date()), "window_end": str(T_END.date()),
                   "window_days": int((T_END - W0).days)}

    # ------------------------------------------------------------ 2. overall
    sep("2. Overall survival: how long does a listed URL stay online?")
    s = km_summary(coh["duration"].to_numpy(), coh["event"].to_numpy(), "all")
    R["overall"] = {k: v for k, v in s.items() if not k.startswith("_")}
    log("  estimator: %s" % s["estimator"])
    for t in (0.5, 1, 2, 7, 14, 30):
        if "S_%g" % t in s:
            log("    S(%5.1f d) = %.4f" % (t, s["S_%g" % t]))
    log("  median time online after listing: %.2f days (%.1f h)"
        % (s["median"], s["median"] * 24))

    log("")
    log("  BRACKET for the %d untimed events, placed at both ends of [0, t_cens]:"
        % (len(untimed) + len(neg)))
    br = {}
    for tag, dur_extra in (("all at t=0 (fastest)", 0.0), ("all at t_cens (slowest)", None)):
        dd = coh[["duration", "event"]].copy()
        if len(untimed) or len(neg):
            extra = pd.concat([
                pd.DataFrame({"duration": (np.zeros(len(untimed)) if dur_extra == 0.0
                                           else untimed["t_cens"].to_numpy()),
                              "event": True}),
                pd.DataFrame({"duration": (np.zeros(len(neg)) if dur_extra == 0.0
                                           else neg["t_cens"].to_numpy()),
                              "event": True}),
            ], ignore_index=True)
            dd = pd.concat([dd, extra], ignore_index=True)
        r = km_summary(dd["duration"].to_numpy(), dd["event"].to_numpy(), tag,
                       checkpoints=(7,))
        br[tag] = {"n": r["n"], "median": round(r["median"], 3),
                   "S_7d": round(r.get("S_7", float("nan")), 4)}
        log("    %-24s n=%d  median=%.2f d  S(7d)=%.4f"
            % (tag, r["n"], r["median"], r.get("S_7", float("nan"))))
    R["untimed_bracket"] = br
    log("")
    log("  Read carefully: every duration is a LOWER BOUND on survival, because")
    log("  `last_online` is the last sighting, not the takedown instant.")

    # ------------------------------------------------------- 3. covariates
    sep("3. Building URL-, payload- and infrastructure-level covariates")
    coh["host"] = [host_of(x) for x in coh["url"].astype(str)]
    coh["ip_based"] = [_IPV4.match(h) is not None for h in coh["host"]]
    coh["block"] = [infra_block(h) for h in coh["host"]]
    log("  distinct hosts in cohort: %d ; distinct infrastructure blocks: %d"
        % (coh["host"].nunique(), coh["block"].nunique()))
    log("  IP-literal URLs: %d (%.1f%%) -- so the host co-location analysis is"
        % (int(coh["ip_based"].sum()), 100.0 * coh["ip_based"].mean()))
    log("  predominantly an IP-block analysis, which is the right operator unit.")
    R["ip_based_pct"] = round(100.0 * float(coh["ip_based"].mean()), 2)

    # threat is degenerate here -- establish it, do not assume a usable stratum.
    th = coh["threat"].fillna("(none)")
    log("")
    log("  `threat` values in the cohort: %s" % dict(th.value_counts().head(8)))
    log("  -> %d distinct value(s)." % th.nunique())
    R["threat_levels"] = {str(k): int(v) for k, v in th.value_counts().items()}

    # tag vocabulary -> payload / family
    tag_lists = coh["tags"].fillna("").apply(
        lambda x: [p.strip().lower() for p in str(x).split(",") if p.strip()])
    coh["n_tags"] = tag_lists.apply(len)
    vocab = Counter(t for L in tag_lists for t in L)
    log("")
    log("  top 20 tags: %s" % dict(vocab.most_common(20)))
    R["tag_vocab_top"] = {k: int(v) for k, v in vocab.most_common(30)}

    def payload_of(L):
        for t in L:
            if t in PAYLOAD:
                return t
        return "(none)"

    def family_of(L):
        for t in L:
            if t not in PAYLOAD and not _ARCH.match(t):
                return t
        return "(unknown)"

    coh["payload"] = tag_lists.apply(payload_of)
    coh["family"] = tag_lists.apply(family_of)
    log("  payload (stated rule: first tag in the payload vocabulary):")
    log("    %s" % dict(coh["payload"].value_counts().head(10)))
    log("  family (stated rule: first tag outside it):")
    log("    %s" % dict(coh["family"].value_counts().head(10)))

    # co-location
    coh["n_urls_block"] = coh.groupby("block")["id"].transform("size")
    full = u.assign(block=[infra_block(host_of(x)) for x in u["url"].astype(str)]) \
             .groupby("block")["id"].size()
    coh["n_urls_block_full"] = coh["block"].map(full).fillna(1).astype(int)
    log("")
    log("  URLs per block (window):  median=%g p90=%g max=%d"
        % (coh["n_urls_block"].median(), coh["n_urls_block"].quantile(.9),
           coh["n_urls_block"].max()))
    log("  URLs per block (feed):    median=%g p90=%g max=%d"
        % (coh["n_urls_block_full"].median(), coh["n_urls_block_full"].quantile(.9),
           coh["n_urls_block_full"].max()))
    rep = coh["reporter"].fillna("(none)").astype(str)
    coh["reporter_anon"] = rep.str.lower().isin(["anonymous", "(none)", ""])
    vol = rep.value_counts()
    coh["reporter_volume"] = rep.map(vol).fillna(1).astype(int)
    log("")
    log("  reporters: %d distinct ; top 8: %s"
        % (rep.nunique(), dict(vol.head(8))))
    log("  top 5 reporters filed %.1f%% of the cohort"
        % (100.0 * vol.head(5).sum() / len(coh)))
    log("  tags per URL: %s" % dict(coh["n_tags"].value_counts().head(8)))

    # ------------------------------------------------- 4. payload / family
    sep("4. Does survival differ by payload type or malware family?")
    for col, lbl in (("payload", "payload"), ("family", "family")):
        top = coh[col].value_counts().head(6).index.tolist()
        g = np.where(coh[col].isin(top), coh[col], "other")
        rows = []
        for gg in top + ["other"]:
            sub = coh[g == gg]
            if not len(sub):
                continue
            r = km_summary(sub["duration"].to_numpy(), sub["event"].to_numpy(), gg,
                           checkpoints=(1, 7))
            rows.append({"group": gg, "n": len(sub), "median_days": round(r["median"], 3),
                         "S_1d": round(r.get("S_1", float("nan")), 4),
                         "S_7d": round(r.get("S_7", float("nan")), 4)})
        tdf = pd.DataFrame(rows).sort_values("n", ascending=False)
        log("")
        log("  by %s:" % lbl)
        log(tdf.to_string(index=False))
        lr = logrank(g, coh["duration"], coh["event"], lbl)
        R["by_" + lbl] = {"table": tdf.to_dict("records"), "logrank": lr}

    # ----------------------------------------------------- 5. co-location
    sep("5. Does sharing an infrastructure block buy survival?")
    log("  Direction is NOT assumed. A block carrying many URLs can go either way:")
    log("  one takedown removes all of them at once (faster per URL), or a large")
    log("  footprint indicates an operator who defends uptime (slower). Two-sided.")
    bins = [0, 1, 2, 5, 20, 100, 10 ** 9]
    labs = ["1", "2", "3-5", "6-20", "21-100", "100+"]
    coh["block_bin"] = pd.cut(coh["n_urls_block"], bins, labels=labs)
    rows = []
    for g in labs:
        sub = coh[coh["block_bin"].astype(str) == g]
        if not len(sub):
            continue
        r = km_summary(sub["duration"].to_numpy(), sub["event"].to_numpy(), g,
                       checkpoints=(1, 7))
        rows.append({"urls_in_block": g, "n": len(sub), "median_days": round(r["median"], 3),
                     "S_1d": round(r.get("S_1", float("nan")), 4),
                     "S_7d": round(r.get("S_7", float("nan")), 4)})
    bdf = pd.DataFrame(rows)
    log("")
    log(bdf.to_string(index=False))
    lr = logrank(coh["block_bin"].astype(str), coh["duration"], coh["event"], "block_size")
    R["by_block_size"] = {"table": bdf.to_dict("records"), "logrank": lr}

    # --------------------------------------------------------- 6. tags
    sep("6. Does functional multiplicity (tag count) buy survival?")
    rows = []
    for g in sorted(coh["n_tags"].clip(upper=3).unique()):
        sub = coh[coh["n_tags"].clip(upper=3) == g]
        r = km_summary(sub["duration"].to_numpy(), sub["event"].to_numpy(), str(g),
                       checkpoints=(7,))
        rows.append({"n_tags": int(g), "n": len(sub),
                     "median_days": round(r["median"], 3),
                     "S_7d": round(r.get("S_7", float("nan")), 4)})
    gdf = pd.DataFrame(rows)
    log(gdf.to_string(index=False))
    lr = logrank(coh["n_tags"].clip(upper=3), coh["duration"], coh["event"], "n_tags")
    R["by_tags"] = {"table": gdf.to_dict("records"), "logrank": lr}

    # ------------------------------------------------- 7. temporal trend
    sep("7. Is takedown getting faster or slower across the window?")
    log("  A naive median-by-week is confounded: later cohorts have shorter")
    log("  follow-up. This uses a FIXED 14-day horizon and only cohorts with a")
    log("  full 14 days of follow-up, which removes the confound by construction.")
    H = 14.0
    elig = coh[coh["t_cens"] >= H].copy()
    elig["down14"] = elig["event"] & (elig["t_event"] <= H)
    elig["days_in"] = (elig["added"] - W0).dt.total_seconds() / 86400.0
    elig["wk"] = (elig["days_in"] // 7).astype(int)
    log("  eligible cohorts: n=%d (%.1f%% of cohort)"
        % (len(elig), 100.0 * len(elig) / len(coh)))
    wk = elig.groupby("wk").agg(n=("id", "size"), down14=("down14", "sum"))
    wk["rate_pct"] = (100.0 * wk["down14"] / wk["n"]).round(1)
    log(wk.to_string())
    trend = {}
    try:
        import statsmodels.api as sm
        X = sm.add_constant(elig["days_in"].to_numpy(dtype=float))
        m = sm.Logit(elig["down14"].to_numpy(dtype=float), X).fit(disp=0)
        b, se = float(m.params[1]), float(m.bse[1])
        trend = {"or_per_day": float(np.exp(b)),
                 "ci_low": float(np.exp(b - 1.96 * se)),
                 "ci_high": float(np.exp(b + 1.96 * se)),
                 "p": float(m.pvalues[1]), "n": int(len(elig))}
        log("  logistic trend on days-since-window-start:")
        log("    OR per day = %.4f  95%% CI [%.4f, %.4f]  p=%.3g"
            % (trend["or_per_day"], trend["ci_low"], trend["ci_high"], trend["p"]))
        log("    OR>1 => takedown became MORE likely over the window (faster)")
    except Exception:  # noqa: BLE001
        log("  !! trend test failed:")
        for ln in traceback.format_exc().splitlines():
            log("     " + ln)
    R["trend_14d"] = {"table": wk.reset_index().to_dict("records"), "logit": trend}

    # ------------------------------------------------------- 8. Cox PH
    sep("8. Cox proportional hazards: which features matter jointly?")
    d = coh.copy()
    d["log_block"] = np.log1p(d["n_urls_block"])
    d["log_block_full"] = np.log1p(d["n_urls_block_full"])
    d["log_reporter_vol"] = np.log1p(d["reporter_volume"])
    d["ip_based_i"] = d["ip_based"].astype(int)
    d["reporter_anon_i"] = d["reporter_anon"].astype(int)
    d["n_tags_c"] = d["n_tags"].clip(upper=3)

    def dummies(col, k):
        top = d[col].value_counts().head(k).index.tolist()
        dd = pd.get_dummies(np.where(d[col].isin(top), d[col], "other"),
                            prefix=col, drop_first=True).astype(float)
        return dd

    fam = dummies("family", 6)
    pay = dummies("payload", 6)
    d = pd.concat([d, fam, pay], axis=1)
    fixed = ["n_tags_c", "log_reporter_vol", "ip_based_i", "reporter_anon_i"]
    fixed = [c for c in fixed if d[c].nunique() > 1]
    extra = list(fam.columns) + list(pay.columns)

    cox_res = {}
    try:
        from lifelines import CoxPHFitter
        from lifelines.statistics import proportional_hazard_test
        for tag, col in (("window", "log_block"), ("whole_feed", "log_block_full")):
            mm = [col] + fixed + extra
            cf = d[["duration", "event"] + mm].dropna()
            # Standardise to 1 SD so a log-scaled count count and a 0/1 flag sit
            # on a comparable scale in the table.
            z = cf.copy()
            for c in mm:
                sd = float(cf[c].std())
                if sd > 0:
                    z[c] = (z[c] - cf[c].mean()) / sd
            cph = CoxPHFitter()
            cph.fit(z, duration_col="duration", event_col="event")
            log("")
            log("  --- co-location measured over: %s ---" % tag)
            log("  n=%d  events=%d  concordance=%.4f"
                % (len(z), int(z["event"].sum()), cph.concordance_index_))
            smry = cph.summary[["exp(coef)", "exp(coef) lower 95%",
                                "exp(coef) upper 95%", "p"]]
            log(smry.round(4).to_string())
            ph = proportional_hazard_test(cph, z, time_transform="rank")
            phs = {k: float(v) for k, v in ph.summary["p"].items()}
            viol = [k for k, v in phs.items() if v < 0.05]
            log("  PH assumption (rank) min p=%.4f ; violations at p<0.05: %d"
                % (min(phs.values()), len(viol)))
            if viol:
                log("    violated: %s" % viol)
            cox_res[tag] = {
                "n": int(len(z)), "events": int(z["event"].sum()),
                "concordance": round(float(cph.concordance_index_), 4),
                "hr_per_sd": {k: round(float(v), 4) for k, v in
                              cph.summary["exp(coef)"].items()},
                "ci_low": {k: round(float(v), 4) for k, v in
                           cph.summary["exp(coef) lower 95%"].items()},
                "ci_high": {k: round(float(v), 4) for k, v in
                            cph.summary["exp(coef) upper 95%"].items()},
                "p": {k: round(float(v), 6) for k, v in cph.summary["p"].items()},
                "ph_violations": viol, "standardised_per_sd": True,
            }
    except Exception:  # noqa: BLE001
        log("  !! Cox failed:")
        for ln in traceback.format_exc().splitlines():
            log("     " + ln)
    R["cox"] = cox_res

    # ------------------------------------------------------------ 9. figure
    sep("9. Figure")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        os.makedirs(FIGS, exist_ok=True)
        fig, ax = plt.subplots(2, 2, figsize=(11, 8.5))
        MAXT = 30

        ts, ss = km_curve(coh["duration"], coh["event"], MAXT)
        ax[0, 0].step(ts, ss, where="post", color="k",
                      label="all URLs (n=%d, %d events)" % (len(coh), int(coh["event"].sum())))
        ax[0, 0].axhline(0.5, ls=":", c="grey", lw=1)
        ax[0, 0].set_title("(a) Overall: time from listing to takedown")
        ax[0, 0].set_xlabel("days since listed")
        ax[0, 0].set_ylabel("S(t) = still online")
        ax[0, 0].legend(fontsize=8)
        ax[0, 0].grid(alpha=.3)

        for g in coh["family"].value_counts().head(5).index:
            sub = coh[coh["family"] == g]
            if len(sub) > 100:
                t_, s_ = km_curve(sub["duration"], sub["event"], MAXT)
                ax[0, 1].step(t_, s_, where="post", label="%s (n=%d)" % (g[:22], len(sub)))
        ax[0, 1].set_title("(b) By inferred malware family (from tags)")
        ax[0, 1].set_xlabel("days since listed")
        ax[0, 1].legend(fontsize=7)
        ax[0, 1].grid(alpha=.3)

        for g in ["1", "3-5", "21-100", "100+"]:
            sub = coh[coh["block_bin"].astype(str) == g]
            if len(sub) > 100:
                t_, s_ = km_curve(sub["duration"], sub["event"], MAXT)
                ax[1, 0].step(t_, s_, where="post",
                              label="%s URL(s) in block (n=%d)" % (g, len(sub)))
        ax[1, 0].set_title("(c) By URLs sharing the /24 or host")
        ax[1, 0].set_xlabel("days since listed")
        ax[1, 0].legend(fontsize=7)
        ax[1, 0].grid(alpha=.3)

        ax[1, 1].errorbar(wk.index * 7 + 3.5, wk["rate_pct"],
                          yerr=1.96 * np.sqrt(wk["rate_pct"] / 100 * (1 - wk["rate_pct"] / 100)
                                               / wk["n"]) * 100,
                          fmt="o-", capsize=3)
        ax[1, 1].set_title("(d) Takedown within 14 days, by cohort week")
        ax[1, 1].set_xlabel("days since window start (cohorts with full 14d follow-up)")
        ax[1, 1].set_ylabel("% taken down within 14 days")
        ax[1, 1].grid(alpha=.3)
        fig.tight_layout()
        for ext in ("png", "pdf"):
            fp = os.path.join(FIGS, "E0_infra_takedown.%s" % ext)
            fig.savefig(fp, dpi=160)
            log("  wrote %s" % fp)
        plt.close(fig)
    except Exception:  # noqa: BLE001
        log("  !! figure failed:")
        for ln in traceback.format_exc().splitlines():
            log("     " + ln)

    # ------------------------------------------------------------ 10. verdict
    sep("10. VERDICT -- what E0 establishes, and what it does not")
    log("  ESTABLISHED (within the observation window, with n stated):")
    log("    * median time online after listing: %.2f days (%.1f h), n=%d, %.1f%% events"
        % (s["median"], s["median"] * 24, len(coh), 100.0 * coh["event"].mean()))
    log("    * S(1d)=%.3f  S(7d)=%.3f  S(30d)=%.3f -- fast for most, a long tail"
        % (s.get("S_1", np.nan), s.get("S_7", np.nan), s.get("S_30", np.nan)))
    log("    * group contrasts are tested above by log-rank and jointly by Cox,")
    log("      with the proportional-hazards assumption checked rather than assumed.")
    log("  NOT ESTABLISHED:")
    log("    * absolute survival -- durations are lower bounds (last sighting, not")
    log("      takedown).")
    log("    * long-run persistence -- the feed's retention window forbids it (C-29).")
    log("    * causality -- these are associations among co-observed URL features.")
    log("    * `threat`-type contrasts -- the cohort holds %d threat value(s), so"
        % th.nunique())
    log("      payload and family are substituted via a stated tag rule.")
    R["limits"] = [
        "duration is a lower bound (last_online = last sighting, not takedown)",
        "detection cadence unpublished; event-time resolution unknown",
        "%d untimed events bracketed, not dropped silently" % (len(untimed) + len(neg)),
        "co-location measured within the observation window (whole-feed sensitivity given)",
        "date_added = blocklist entry time, not URL creation time",
        "short-horizon only; retention window forbids long-run survival claims",
        "threat column is degenerate; family/payload inferred from tags by stated rule",
    ]

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "04_E0_infra_takedown.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    with open(os.path.join(RESULTS, "04_E0_infra_takedown.json"), "w",
              encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, default=str)
    log("\nwrote %s/04_E0_infra_takedown.{txt,json}" % RESULTS)
    log("E0_DONE")


if __name__ == "__main__":
    sys.exit(main())
