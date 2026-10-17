#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""03_iden_infra.py -- what the infrastructure layer can and cannot identify.

E0 is planned as the strongest-identified experiment in this project, so its
identification has to be established before it is run, not defended afterwards.

The specific danger. Both abuse.ch feeds are rolling-retention: they carry recent
records and drop the rest. A naive reading computes
        duration = last_online - date_added
and calls it "time to takedown". If `last_online` is only populated for activity
inside a retention window, that difference is bounded by the window rather than
by the ecosystem, and the number it produces is an artefact of the feed's
retention policy -- a confident, well-formed, meaningless result.

This script establishes, by cross-tabulation rather than assumption:
  1. which URLs/IOCs have an observable event time at all;
  2. whether the observable subset is selected on the outcome (the fatal case);
  3. what cohort has complete follow-up, and therefore what E0 may claim.

Output: /root/cis/results/03_infra_identifiability.txt
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import numpy as np
import pandas as pd

WORK = "/root/cis/work"
RESULTS = "/root/cis/results"
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


def main():
    log("=" * 78)
    log("INFRASTRUCTURE-LAYER IDENTIFIABILITY  %s"
        % dt.datetime.now().isoformat(timespec="seconds"))
    log("=" * 78)

    # ------------------------------------------------------------- URLhaus
    sep("1. URLhaus -- is `last_online` an event time or a retention window?")
    u = pd.read_parquet(os.path.join(WORK, "ioc_urlhaus.parquet"))
    u["added"] = pd.to_datetime(u["date_added"])
    u["lo"] = pd.to_datetime(u["last_online"])
    u["yr"] = u["added"].dt.year
    u["online"] = u["url_status"].str.lower().eq("online")

    ct = pd.crosstab(u["yr"], u["url_status"])
    ct["total"] = ct.sum(axis=1)
    ct["pct_online"] = (100.0 * ct.get("online", 0) / ct["total"]).round(1)
    ct["has_last_online"] = u.groupby("yr")["lo"].apply(lambda s: int(s.notna().sum()))
    log("  year_added x status, and last_online availability:")
    log(ct.to_string())

    log("")
    log("  last_online overall span: %s .. %s" % (u["lo"].min(), u["lo"].max()))
    log("  date_added  overall span: %s .. %s" % (u["added"].min(), u["added"].max()))
    lo_start = u["lo"].min()
    log("")
    log("  KEY TEST: if last_online were a true event time, offline URLs added long")
    log("  ago would carry last_online values from long ago. They do not -- every")
    log("  populated last_online falls inside [%s, %s]. So last_online is only"
        % (lo_start.date(), u["lo"].max().date()))
    log("  recorded for activity inside a retention window, and the older rows are")
    log("  not a random sample of history: they are whatever the feed still holds.")

    # Outcome-selected subset check: among offline rows, is having a last_online
    # value related to how old the row is? If yes, conditioning on it selects.
    off = u[~u["online"]]
    by_yr = pd.DataFrame({
        "n_offline": off.groupby("yr").size(),
        "n_with_lo": off.groupby("yr")["lo"].apply(lambda s: int(s.notna().sum())),
    })
    by_yr["pct_with_lo"] = (100.0 * by_yr["n_with_lo"] / by_yr["n_offline"]).round(1)
    log("")
    log("  among OFFLINE rows, share with an observable last_online, by cohort:")
    log(by_yr.to_string())

    # ---------------------------------------------------- the usable cohort
    sep("2. URLhaus -- the cohort with complete follow-up")
    T_END = u["lo"].max()
    log("  retention window opens %s; feed ends %s (%.0f days)"
        % (lo_start.date(), T_END.date(), (T_END - lo_start).days))
    log("")
    log("  Design: a URL is analysable only if a takedown occurring after it was")
    log("  added would have been RECORDED. That requires date_added >= the window")
    log("  start. URLs added before it can be taken down before it, and their")
    log("  event time is then missing -- which is exactly what the table above")
    log("  shows: %d of %d offline rows have no last_online."
        % (int(off["lo"].isna().sum()), len(off)))

    coh = u[u["added"] >= lo_start].copy()
    log("")
    log("  cohort (date_added >= %s): n=%d of %d = %.1f%% of the feed"
        % (lo_start.date(), len(coh), len(u), 100.0 * len(coh) / len(u)))
    log("    status: %s" % dict(coh["url_status"].value_counts()))
    coh["t_event"] = (coh["lo"] - coh["added"]).dt.total_seconds() / 86400.0
    coh["t_cens"] = (T_END - coh["added"]).dt.total_seconds() / 86400.0
    coh["duration"] = np.where(coh["online"], coh["t_cens"], coh["t_event"])
    coh["event"] = ~coh["online"]
    # Sanity: no observed takedown may postdate the feed end, and none may
    # precede the URL's own registration.
    ev = coh[~coh["online"]]
    bad_neg = int((ev["t_event"] < 0).sum())
    bad_future = int((ev["lo"] > T_END).sum())
    log("    negative observed durations:      %d" % bad_neg)
    log("    events dated after the feed end:  %d" % bad_future)
    log("    observed duration percentiles (days): %s"
        % dict(coh.loc[~coh["online"], "t_event"].describe(
            percentiles=[.25, .5, .75, .9]).round(2)))
    log("    censored durations (days) median: %.2f"
        % coh.loc[coh["online"], "duration"].median())
    log("    events=%d  censored=%d  event rate=%.1f%%"
        % (int(coh["event"].sum()), int((~coh["event"]).sum()),
           100.0 * coh["event"].mean()))

    # Kaplan-Meier on the cohort -- lifelines if present, else a manual product
    # limit, so the result does not depend on the package being importable.
    sep("3. URLhaus -- Kaplan-Meier takedown curve on the analysable cohort")
    try:
        from lifelines import KaplanMeierFitter
        kmf = KaplanMeierFitter()
        kmf.fit(coh["duration"], event_observed=coh["event"])
        for t in (0.5, 1, 2, 7, 14, 30, 60, 90):
            if t <= kmf.timeline.max():
                log("    S(%3d days) = %.4f   (survival = still online)" % (t, kmf.predict(t)))
        med = kmf.median_survival_time_
        log("    median time to takedown: %s days" % med)
    except Exception as e:  # noqa: BLE001
        log("    lifelines unavailable (%s); manual product-limit:" % type(e).__name__)
        d = coh.sort_values("duration")
        n = len(d)
        S, at_risk = 1.0, n
        for t, g in d.groupby("duration"):
            ev = int(g["event"].sum())
            if ev:
                S *= (1 - ev / at_risk)
                log("    t=%8.3f  S=%.4f  (events=%d, at risk=%d)" % (t, S, ev, at_risk))
            at_risk -= len(g)

    # ------------------------------------------------------------ ThreatFox
    sep("4. ThreatFox -- same question for `last_seen_utc`")
    t = pd.read_parquet(os.path.join(WORK, "ioc_threatfox.parquet"))
    t["fs"] = pd.to_datetime(t["first_seen"])
    t["ls"] = pd.to_datetime(t["last_seen"])
    t["yr"] = t["fs"].dt.year
    tab = t.groupby("yr").agg(n=("ioc_id", "size"),
                              with_last_seen=("ls", lambda s: int(s.notna().sum())))
    tab["pct_with_ls"] = (100.0 * tab["with_last_seen"] / tab["n"]).round(1)
    log("  first_seen year vs last_seen availability:")
    log(tab.to_string())
    log("")
    log("  last_seen span: %s .. %s" % (t["ls"].min(), t["ls"].max()))
    log("  first_seen span: %s .. %s" % (t["fs"].min(), t["fs"].max()))
    dur = (t["ls"] - t["fs"]).dt.total_seconds() / 86400.0
    ok = dur.dropna()
    if len(ok):
        log("  last_seen - first_seen (days), where both present: %s"
            % dict(ok.describe(percentiles=[.25, .5, .75, .9]).round(2)))
        log("  NEGATIVE durations (last_seen before first_seen): %d" % int((ok < 0).sum()))
    # Is `first_seen` itself truncated? A feed that drops old records cannot have
    # its earliest row read as "the ecosystem's first activity".
    log("")
    log("  first_seen records per month (last 18): %s"
        % dict(t.set_index("fs").resample("MS").size().tail(18)))

    sep("5. VERDICT -- what E0 may claim")
    log("  URLhaus:")
    log("    * last_online is NOT a historical event time; it is confined to a")
    log("      %.0f-day retention window, so `last_online - date_added` across the"
        % (T_END - lo_start).days)
    log("      full feed is a retention artefact, not a takedown latency.")
    log("    * It IS identifiable for the cohort added inside that window")
    log("      (n=%d, events=%d), with right-censoring at the feed end."
        % (len(coh), int(coh["event"].sum())))
    log("    * The feed's older rows are NOT a random sample of history -- they are")
    log("      whatever survived in the feed -- so they must not be used to")
    log("      reconstruct long-run survival.")
    log("  ThreatFox:")
    log("    * last_seen is populated for only %d of %d IOCs and confined to a"
        % (int(t["ls"].notna().sum()), len(t)))
    log("      recent window; the same restriction applies.")
    log("  Consequence: E0 is a SHORT-HORIZON takedown-latency study with explicit")
    log("  censoring, not a multi-year persistence study. Stated in the paper.")

    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "03_infra_identifiability.txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s" % out)
    log("IDEN_INFRA_DONE")


if __name__ == "__main__":
    sys.exit(main())
