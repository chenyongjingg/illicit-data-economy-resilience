#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""05_E0_robust.py -- E0 validity checks, run before any E0 result is reported.

E0's headline association is "URLs sharing a larger infrastructure block survive
longer". Three things could produce that association without any infrastructure
mechanism existing, and each is tested here rather than argued about:

1. NON-INDEPENDENCE. URLhaus probes a host and writes what it saw. If a single
   probe stamps `last_online` onto every URL on that host, then co-hosted URLs do
   not carry 36,262 independent event times -- they carry a few thousand, and
   every log-rank chi-square and Cox z-score is inflated by the design effect.
   TEST: within blocks of size >= 2, how often is `last_online` a single shared
   value? Same question for `date_added`.

2. SUBMITTER CONFOUNDING. One reporter filed 29.6% of the cohort. If reporters
   submit in bulk from particular IP ranges, then "large block" and "particular
   reporter" are the same variable, and the block-size effect is a statement
   about who submitted, not about the infrastructure.
   TEST: reporter x block-size cross-tabulation; then re-run the block-size
   contrast (a) within the single largest reporter and (b) stratified by reporter
   in a Cox model, which absorbs submitter identity entirely.

3. HETEROGENEOUS TAGS. URLhaus tags mix payload type (`elf`), architecture
   (`mips`), malware family (`mozi`), URL character (`botnetdomain`, `opendir`),
   detection provenance (`censys`) and submitter tooling (`ua-wget`). Treating
   them as one partition, as E0 first did, invents a "family" variable whose
   levels are not commensurable.
   TEST: classify each tag by role and report the classification; then contrast
   each top tag as its own binary stratum, which asserts no partition.

Also reports effective sample size and cluster-robust standard errors.

Output: results/05_E0_robustness.{txt,json}
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
_L: list[str] = []
R: dict = {}

# Tag roles, assigned by inspection of the observed vocabulary. The rule is
# stated so a reader can disagree with a specific assignment rather than with the
# whole construct.
TAG_ROLE = {
    # payload file type / format
    "elf": "payload", "exe": "payload", "dll": "payload", "sh": "payload",
    "doc": "payload", "docx": "payload", "xls": "payload", "zip": "payload",
    "rar": "payload", "msi": "payload", "apk": "payload", "jar": "payload",
    "js": "payload", "vbs": "payload", "ps1": "payload", "powershell": "payload",
    "hta": "payload", "iso": "payload", "python": "payload", "php": "payload",
    "html": "payload", "ascii": "payload", "binary": "payload",
    # architecture / word size
    "32-bit": "arch", "64-bit": "arch", "mips": "arch", "mips64": "arch",
    "arm": "arch", "arm64": "arch", "sparc": "arch", "x86": "arch",
    "x86-64": "arch", "ppc": "arch", "m68k": "arch", "unknown-arch": "arch",
    # malware family / botnet
    "mozi": "family", "mirai": "family", "gafgyt": "family", "remcosrat": "family",
    "rat": "family", "connectwise": "family", "emotet": "family", "gozi": "family",
    "qakbot": "family", "icedid": "family", "trickbot": "family", "cobalt": "family",
    "amadey": "family", "dropped-by-amadey": "family", "socks5systemz": "family",
    "hajime": "family", "bashlite": "family", "tsunami": "family",
    # character of the URL itself
    "botnetdomain": "url_character", "opendir": "url_character",
    "malware_download": "url_character", "geofenced": "url_character",
    # detection provenance / who found it
    "censys": "provenance", "shodan": "provenance", "urlscan": "provenance",
    "tweetfeed": "provenance",
    # submitter tooling
    "ua-wget": "submitter", "ua-curl": "submitter",
    # `none` is a placeholder meaning "no tags on this URL", not a submitter tool.
    # It was mislabelled `submitter` on the first pass; the median contrast for it
    # (2.12 d vs 1.33 d) is unaffected, only the role label was wrong.
    "none": "placeholder",
}


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


def median_of(dur, ev):
    ts, ss = km_curve(dur, ev)
    return float(ts[np.argmax(ss <= 0.5)]) if (ss <= 0.5).any() else float("inf")


def s_at(dur, ev, t):
    ts, ss = km_curve(dur, ev, max_t=t)
    return float(ss[-1]) if len(ss) else float("nan")


def logrank(g, dur, ev, name):
    if pd.Series(g).nunique() < 2:
        log("  log-rank (%s): not defined, %d group(s)"
            % (name, pd.Series(g).nunique()))
        return None
    try:
        from lifelines.statistics import multivariate_logrank_test
        r = multivariate_logrank_test(dur, g, ev)
        log("  log-rank (%s): chi2=%.1f dof=%d p=%.3g"
            % (name, r.test_statistic, r.degrees_of_freedom, r.p_value))
        return {"chi2": float(r.test_statistic), "dof": int(r.degrees_of_freedom),
                "p": float(r.p_value)}
    except Exception:  # noqa: BLE001
        log("  !! log-rank (%s) failed: %s" % (name, traceback.format_exc().splitlines()[-1]))
        return None


def build():
    u = pd.read_parquet(os.path.join(WORK, "ioc_urlhaus.parquet"))
    u["added"] = pd.to_datetime(u["date_added"], errors="coerce")
    u["lo"] = pd.to_datetime(u["last_online"], errors="coerce")
    u["online"] = u["url_status"].str.lower().eq("online")
    W0, T_END = u["lo"].min(), u["lo"].max()
    from urllib.parse import urlsplit
    import re
    ipv4 = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

    def host_of(x):
        try:
            return (urlsplit(x if "://" in x else "http://" + x).hostname or "").lower()
        except Exception:  # noqa: BLE001
            return ""

    def block_of(h):
        if ipv4.match(h):
            return "ip24:" + ".".join(h.split(".")[:3])
        return "host:" + h

    u["host"] = [host_of(x) for x in u["url"].astype(str)]
    u["block"] = [block_of(h) for h in u["host"]]
    c = u[u["added"] >= W0].copy()
    c["t_event"] = (c["lo"] - c["added"]).dt.total_seconds() / 86400.0
    c["t_cens"] = (T_END - c["added"]).dt.total_seconds() / 86400.0
    c = c[c["t_event"].notna() & (c["t_event"] >= 0)].copy()
    c["duration"] = np.where(c["online"].to_numpy(), c["t_cens"].to_numpy(),
                             c["t_event"].to_numpy())
    c["event"] = ~c["online"]
    c["n_block"] = c.groupby("block")["id"].transform("size")
    c["n_host"] = c.groupby("host")["id"].transform("size")
    c["reporter"] = c["reporter"].fillna("(none)").astype(str)
    return c, W0, T_END


def main():
    t0 = dt.datetime.now()
    log("=" * 78)
    log("E0 ROBUSTNESS -- is the block-size association an artefact?  %s"
        % t0.isoformat(timespec="seconds"))
    log("=" * 78)
    c, W0, T_END = build()
    log("  cohort n=%d  events=%d" % (len(c), int(c["event"].sum())))
    R["n"] = int(len(c))
    R["events"] = int(c["event"].sum())

    # ---------------------------------------------- 1. non-independence
    sep("1. Are co-hosted URLs independent observations?")
    big = c[c["n_host"] >= 2]
    g = big.groupby("host")
    share_lo = g["lo"].nunique().eq(1).mean()
    share_ad = g["added"].nunique().eq(1).mean()
    share_dur = g["duration"].nunique().eq(1).mean()
    log("  hosts with >=2 URLs: %d, covering %d URLs (%.1f%% of cohort)"
        % (g.ngroups, len(big), 100.0 * len(big) / len(c)))
    log("")
    log("  within such a host, the share where ALL its URLs share one value:")
    log("    `last_online` : %.1f%%" % (100 * share_lo))
    log("    `date_added`  : %.1f%%" % (100 * share_ad))
    log("    `duration`    : %.1f%%" % (100 * share_dur))
    log("")
    log("  If `last_online` is written once per probe, co-hosted URLs share an")
    log("  event time and are ONE observation, not many.")
    R["independence"] = {
        "hosts_ge2": int(g.ngroups), "urls_in_them": int(len(big)),
        "pct_share_last_online": round(100 * float(share_lo), 2),
        "pct_share_date_added": round(100 * float(share_ad), 2),
        "pct_share_duration": round(100 * float(share_dur), 2),
    }

    # effective sample size
    eff_lo = c.groupby(["block", "lo"]).ngroups
    eff_blk = c["block"].nunique()
    log("")
    log("  EFFECTIVE SAMPLE SIZE:")
    log("    rows (URLs):                        %d" % len(c))
    log("    distinct blocks:                    %d" % eff_blk)
    log("    distinct (block, last_online) pairs:%d" % eff_lo)
    log("    -> the honest n for a takedown-time question is nearer the last two")
    log("       numbers than the first. Design effect (URLs per independent unit)")
    log("       ~ %.1fx." % (len(c) / max(eff_lo, 1)))
    R["effective_n"] = {"rows": int(len(c)), "blocks": int(eff_blk),
                        "block_time_pairs": int(eff_lo),
                        "design_effect": round(len(c) / max(eff_lo, 1), 2)}

    # ---------------------------------------------- 2. submitter confounding
    sep("2. Is 'large block' just 'particular reporter'?")
    bins = [0, 1, 2, 5, 20, 100, 10 ** 9]
    labs = ["1", "2", "3-5", "6-20", "21-100", "100+"]
    c["block_bin"] = pd.cut(c["n_block"], bins, labels=labs)
    top_rep = c["reporter"].value_counts().head(8).index.tolist()
    ct = pd.crosstab(c["reporter"].where(c["reporter"].isin(top_rep), "other"),
                     c["block_bin"])
    log("  reporter x block size (counts):")
    log(ct.to_string())
    log("")
    # share of the largest bin contributed by the single largest reporter
    top1 = c["reporter"].value_counts().index[0]
    big_bin = c[c["block_bin"].astype(str) == "100+"]
    log("  reporter '%s' filed %d URLs (%.1f%% of cohort) and %d of the %d URLs"
        % (top1, int((c["reporter"] == top1).sum()),
           100.0 * (c["reporter"] == top1).mean(),
           int((big_bin["reporter"] == top1).sum()), len(big_bin)))
    log("  in the 100+ block bin (%.1f%% of it)."
        % (100.0 * (big_bin["reporter"] == top1).mean()))
    R["reporter_block_crosstab"] = ct.to_dict()
    R["top_reporter"] = {"name": str(top1),
                         "n": int((c["reporter"] == top1).sum()),
                         "pct_cohort": round(100 * float((c["reporter"] == top1).mean()), 2),
                         "pct_of_100plus_bin": round(
                             100 * float((big_bin["reporter"] == top1).mean()), 2)}

    log("")
    log("  (a) block-size contrast WITHIN the single largest reporter only:")
    sub = c[c["reporter"] == top1].copy()
    rows = []
    for g_ in labs:
        s = sub[sub["block_bin"].astype(str) == g_]
        if len(s) < 50:
            continue
        rows.append({"urls_in_block": g_, "n": len(s),
                     "median_days": round(median_of(s["duration"], s["event"]), 3),
                     "S_7d": round(s_at(s["duration"], s["event"], 7), 4)})
    tdf = pd.DataFrame(rows)
    log(tdf.to_string(index=False))
    lr_within = logrank(sub["block_bin"].astype(str), sub["duration"], sub["event"],
                        "block size within reporter %s" % top1)
    R["within_top_reporter"] = {"reporter": str(top1), "table": tdf.to_dict("records"),
                                "logrank": lr_within}

    log("")
    log("  (b) does block size still span a range inside one reporter? (it must,")
    log("      or the contrast above is degenerate)")
    log("    blocks in that reporter's submissions: n=%d, median URLs/block=%g"
        % (sub["block"].nunique(), sub["n_block"].median()))

    # ---------------------------------------- 3. cluster-robust Cox
    sep("3. Cox with cluster-robust standard errors")
    d = c.copy()
    d["log_block"] = np.log1p(d["n_block"])
    rep_vol = d["reporter"].value_counts()
    d["log_reporter_vol"] = np.log1p(d["reporter"].map(rep_vol).fillna(1))
    tags = d["tags"].fillna("").apply(
        lambda x: {p.strip().lower() for p in str(x).split(",") if p.strip()})
    d["n_tags"] = tags.apply(len)
    d["n_tags_c"] = d["n_tags"].clip(upper=5)
    d["has_elf"] = tags.apply(lambda s: int("elf" in s))
    d["has_mozi"] = tags.apply(lambda s: int("mozi" in s))
    d["has_mirai"] = tags.apply(lambda s: int("mirai" in s))
    d["has_censys"] = tags.apply(lambda s: int("censys" in s))
    d["has_opendir"] = tags.apply(lambda s: int("opendir" in s))
    d["has_botnetdomain"] = tags.apply(lambda s: int("botnetdomain" in s))
    d["top_rep"] = d["reporter"].where(d["reporter"].isin(top_rep), "other")

    cov = ["log_block", "n_tags_c", "log_reporter_vol", "has_elf", "has_mozi",
           "has_mirai", "has_censys", "has_opendir", "has_botnetdomain"]
    res = {}
    try:
        from lifelines import CoxPHFitter

        def fit(df_, cols, label, cluster=None, strata=None):
            f = df_[["duration", "event"] + cols + ([cluster] if cluster else [])
                    + ([strata] if strata else [])].dropna().copy()
            z = f.copy()
            for x in cols:
                sd = float(f[x].std())
                if sd > 0:
                    z[x] = (z[x] - f[x].mean()) / sd
            m = CoxPHFitter()
            m.fit(z, duration_col="duration", event_col="event",
                  cluster_col=cluster, strata=strata)
            se = m.summary[["exp(coef)", "se(coef)", "p"]]
            log("")
            log("  --- %s ---" % label)
            log("  n=%d  events=%d  concordance=%.4f"
                % (len(z), int(z["event"].sum()), m.concordance_index_))
            log(se.round(4).to_string())
            res[label] = {
                "n": int(len(z)), "events": int(z["event"].sum()),
                "concordance": round(float(m.concordance_index_), 4),
                "hr_per_sd": {k: round(float(v), 4) for k, v in
                              m.summary["exp(coef)"].items()},
                "se": {k: round(float(v), 5) for k, v in m.summary["se(coef)"].items()},
                "p": {k: round(float(v), 6) for k, v in m.summary["p"].items()},
            }
            return m

        m0 = fit(d, cov, "IID SEs (as E0 first reported)")
        m1 = fit(d, cov, "clustered by infrastructure block", cluster="block")
        m2 = fit(d, cov, "clustered by reporter", cluster="reporter")
        m3 = fit(d, cov, "stratified by reporter (submitter absorbed)",
                 strata="top_rep")

        log("")
        log("  SE inflation from ignoring clustering (block):")
        for x in cov:
            a = m0.summary.loc[x, "se(coef)"]
            b = m1.summary.loc[x, "se(coef)"]
            log("    %-20s iid=%.5f  clustered=%.5f  ratio=%.2fx"
                % (x, a, b, b / a if a else float("nan")))
        R["se_inflation_block"] = {
            x: round(float(m1.summary.loc[x, "se(coef)"] /
                           m0.summary.loc[x, "se(coef)"]), 3) for x in cov}
    except Exception:  # noqa: BLE001
        log("  !! clustered Cox failed:")
        for ln in traceback.format_exc().splitlines():
            log("     " + ln)
    R["cox"] = res

    # ---------------------------------------------- 4. tag roles
    sep("4. Tags by role -- the vocabulary is not one partition")
    vocab = {}
    for s in c["tags"].fillna(""):
        for p in str(s).split(","):
            p = p.strip().lower()
            if p:
                vocab[p] = vocab.get(p, 0) + 1
    rows = [{"tag": k, "n": v, "role": TAG_ROLE.get(k, "(unclassified)")}
            for k, v in sorted(vocab.items(), key=lambda kv: -kv[1])[:30]]
    tdf = pd.DataFrame(rows)
    log(tdf.to_string(index=False))
    unmapped = [r["tag"] for r in rows if r["role"] == "(unclassified)"]
    log("")
    log("  unclassified tags above: %s" % (unmapped or "none"))
    R["tag_roles"] = {"table": tdf.to_dict("records"), "unclassified": unmapped}

    sep("5. Each top tag as its own binary stratum (no partition asserted)")
    rows = []
    for t in [r["tag"] for r in R["tag_roles"]["table"][:12]]:
        has = c["tags"].fillna("").str.lower().str.contains(
            r"(^|,)\s*%s\s*(,|$)" % t, regex=True)
        if has.sum() < 100 or (~has).sum() < 100:
            continue
        a_m = median_of(c.loc[has, "duration"], c.loc[has, "event"])
        b_m = median_of(c.loc[~has, "duration"], c.loc[~has, "event"])
        a_s = s_at(c.loc[has, "duration"], c.loc[has, "event"], 7)
        b_s = s_at(c.loc[~has, "duration"], c.loc[~has, "event"], 7)
        lr = logrank(has.astype(int), c["duration"], c["event"], t)
        rows.append({"tag": t, "role": TAG_ROLE.get(t, "?"), "n_with": int(has.sum()),
                     "median_with": round(a_m, 3), "median_without": round(b_m, 3),
                     "S7_with": round(a_s, 4), "S7_without": round(b_s, 4),
                     "chi2": (round(lr["chi2"], 1) if lr else None)})
    bdf = pd.DataFrame(rows)
    log("")
    log(bdf.to_string(index=False))
    log("")
    log("  Read this table by ROLE. A `provenance` tag (censys) contrasting with")
    log("  everything else says who found the URL, not what the malware does.")
    R["tag_binary"] = bdf.to_dict("records")

    # ------------------------------------------------------------ verdict
    sep("6. VERDICT -- what survives these checks")
    log("  Independence: %s" % ("co-hosted URLs share last_online in %.1f%% of hosts"
                                % R["independence"]["pct_share_last_online"]))
    log("  Effective n (block x time): %d, vs %d rows (design effect %.1fx)"
        % (R["effective_n"]["block_time_pairs"], len(c),
           R["effective_n"]["design_effect"]))
    if lr_within:
        log("  Block-size contrast WITHIN the largest reporter: chi2=%.1f p=%.3g"
            % (lr_within["chi2"], lr_within["p"]))
    log("  Detail above; the numbers in the report are the clustered ones.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "05_E0_robustness.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    with open(os.path.join(RESULTS, "05_E0_robustness.json"), "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, default=str)
    log("\nwrote %s/05_E0_robustness.{txt,json}" % RESULTS)
    log("E0_ROBUST_DONE")


if __name__ == "__main__":
    sys.exit(main())
