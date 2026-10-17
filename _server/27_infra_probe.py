#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""27_infra_probe.py -- what can the IOC feeds support?

The sprint plan assigns the infrastructure layer to IOC feeds. Two full dumps
were collected from abuse.ch:

  URLhaus   urlhaus_full__csv.txt      id, dateadded, url, url_status,
                                       last_online, threat, tags, link, reporter
  ThreatFox threatfox_full__full.csv   first_seen_utc, ioc_id, ioc_value,
                                       ioc_type, threat_type, fk_malware,
                                       ..., last_seen_utc, confidence_level,
                                       is_compromised, reference, tags, ...
                                       reporter

Only URLhaus advertises a removal signal (`url_status` online/offline plus
`last_online`). ThreatFox's `last_seen_utc` looked EMPTY in a three-row peek,
which if true across the file means there is no removal observable and the
feed cannot support a persistence question at all -- the same trap that killed
E4's `tenuredays`/`censored` columns (C-26/C-40 family) and it must be checked
rather than assumed in either direction.

A three-row peek is not evidence about 100,000 rows. This probe measures:

  * populated rate of every time column, by status;
  * the dateadded / first_seen ranges, which decide whether the dump is a
    complete history or a recent window (left-truncation);
  * the observable that would actually be used, and how much of it is missing.

Both files are small enough to read whole; the care here is about meaning, not
memory.
"""
from __future__ import annotations

import io
import os

import numpy as np
import pandas as pd

RECON = "/root/cis/data/_recon/abusech"
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


def read_abusech(path):
    """abuse.ch dumps put the real CSV header inside a comment line.

    Two things this has to get right, and the first version got both wrong:
      * the header is a COMMENT line, so it must start with '#' -- an earlier
        version tested `startswith('"')` AFTER stripping the '#', which made the
        first DATA row (also quoted, also comma-bearing) a valid match. It
        silently used one row of data as the column names and the failure only
        surfaced later as KeyError: 'url_status'.
      * URLhaus's header is unquoted (`# id,dateadded,url,...`) while
        ThreatFox's is quoted (`# "first_seen_utc","ioc_id",...`), so the parser
        must handle both.
    The detected header is printed so a mis-parse cannot pass unremarked.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    hdr_i, header = None, None
    for i, ln in enumerate(lines[:40]):
        if not ln.lstrip().startswith("#"):
            continue                      # a data line can never be the header
        s = ln.lstrip().lstrip("#").strip()
        if s and "," in s:
            hdr_i, header = i, s
            break
    if hdr_i is None:
        raise SystemExit("no header found in %s" % path)
    cols = [c.strip().strip('"') for c in header.split(",")]
    print("  [header] %d cols from line %d: %s"
          % (len(cols), hdr_i + 1, cols[:5]), flush=True)
    # skipinitialspace=True is load-bearing. ThreatFox separates fields with
    # `", "` (comma AND a space). With the default skipinitialspace=False the
    # space becomes part of the next field, so its opening quote is no longer at
    # field start, so the quote is literal and any comma INSIDE it -- e.g.
    # "RemcosRAT,Remvio,Socmer" -- splits the field. The parse then silently
    # produces 18 columns for a 15-column row. URLhaus uses bare commas and is
    # unaffected either way.
    df = pd.read_csv(io.StringIO("".join(lines[hdr_i + 1:])), header=None,
                     names=cols, low_memory=False, skipinitialspace=True)
    return df, hdr_i + 1


def main():
    log("=" * 78)
    log("Infrastructure layer: what do the IOC feeds support?")
    log("=" * 78)

    # ------------------------------------------------------------- URLhaus
    u, skip = read_abusech(os.path.join(RECON, "urlhaus_full__csv.txt"))
    log("\n  URLhaus: %d data rows (skipped %d comment/header lines)"
        % (len(u), skip))
    log("  columns: %s" % list(u.columns))
    need = ["id", "dateadded", "url", "url_status", "last_online", "threat"]
    missing = [c for c in need if c not in u.columns]
    if missing:
        raise SystemExit("[guard] URLhaus parsed without required columns %s -- "
                         "the header was not detected correctly" % missing)

    sep("URLhaus -- 1. url_status, the removal signal")
    vc = u["url_status"].value_counts(dropna=False)
    log(vc.to_string())
    rate = u["url_status"].value_counts(normalize=True) * 100
    log("  offline share: %.2f%%" % rate.get("offline", 0.0))

    sep("URLhaus -- 2. Is `last_online` populated, and for whom?")
    lo = u["last_online"].astype(str).str.strip()
    populated = (lo != "") & (lo.str.lower() != "none") & (lo != "nan")
    log("  last_online populated overall: %d / %d (%.2f%%)"
        % (int(populated.sum()), len(u), 100.0 * populated.mean()))
    log("  by url_status:")
    for s in u["url_status"].dropna().unique():
        m = u["url_status"] == s
        log("    %-10s n=%7d  populated=%7d (%.2f%%)"
            % (s, int(m.sum()), int(populated[m].sum()),
               100.0 * populated[m].mean()))
    log("")
    log("  ★ This is the decisive number. If `last_online` is empty for offline")
    log("  URLs, the removal time is unobserved and no duration can be formed.")

    sep("URLhaus -- 3. dateadded range and left-truncation")
    da = pd.to_datetime(u["dateadded"], errors="coerce")
    log("  dateadded: min=%s max=%s ; NaT=%d"
        % (da.min(), da.max(), int(da.isna().sum())))
    log("  per-year counts:")
    log(da.dt.year.value_counts().sort_index().to_string())
    log("")
    log("  If the dump retains everything ever added, the earliest years should")
    log("  be present. A dump that starts only recently is a window, not a")
    log("  history, and a duration measured from it is left-truncated.")

    sep("URLhaus -- 4. threat types and reporters")
    log("  threat (top 8):")
    log(u["threat"].value_counts().head(8).to_string())
    log("")
    log("  distinct reporters: %d ; distinct urls: %d ; distinct ids: %d"
        % (u["reporter"].nunique(), u["url"].nunique(), u["id"].nunique()))
    log("  duplicate url rows: %d" % int(u["url"].duplicated().sum()))

    sep("URLhaus -- 5. The usable outcome, if last_online is populated")
    d = u[populated & (u["url_status"] == "offline")].copy()
    if len(d):
        dur = (pd.to_datetime(d["last_online"], errors="coerce") - da[d.index])
        dur_d = dur.dt.total_seconds() / 86400.0
        log("  offline URLs with a parseable last_online: %d" % len(d))
        log("  lifetime (days): min=%.3f p25=%.2f p50=%.2f p75=%.2f p90=%.2f"
            " max=%.1f"
            % (dur_d.min(), dur_d.quantile(.25), dur_d.median(),
               dur_d.quantile(.75), dur_d.quantile(.90), dur_d.max()))
        log("  negative durations: %d (would indicate a broken join)"
            % int((dur_d < 0).sum()))
        log("  duration == 0 (added and last seen the same moment): %d (%.1f%%)"
            % (int((dur_d == 0).sum()), 100.0 * (dur_d == 0).mean()))

    # ----------------------------------------------------------- ThreatFox
    log("")
    log("=" * 78)
    t, skip2 = read_abusech(os.path.join(RECON, "threatfox_full__full.csv"))
    log("  ThreatFox: %d data rows (skipped %d comment/header lines)"
        % (len(t), skip2))
    log("  columns: %s" % list(t.columns))

    sep("ThreatFox -- 1. Are the time columns populated?")
    for c in ("first_seen_utc", "last_seen_utc"):
        s = t[c].astype(str).str.strip()
        p = (s != "") & (s.str.lower() != "none") & (s != "nan")
        log("  %-16s populated %7d / %d (%.2f%%)"
            % (c, int(p.sum()), len(t), 100.0 * p.mean()))
    log("")
    log("  ★ If last_seen_utc is empty throughout, there is NO removal")
    log("  observable and ThreatFox cannot support a persistence analysis.")

    sep("ThreatFox -- 2. composition")
    log("  ioc_type (top 8):")
    log(t["ioc_type"].value_counts().head(8).to_string())
    log("")
    log("  threat_type (top 8):")
    log(t["threat_type"].value_counts().head(8).to_string())
    fs = pd.to_datetime(t["first_seen_utc"], errors="coerce")
    log("")
    log("  first_seen_utc: min=%s max=%s ; NaT=%d"
        % (fs.min(), fs.max(), int(fs.isna().sum())))
    log("  per-year counts:")
    log(fs.dt.year.value_counts().sort_index().to_string())
    log("")
    log("  confidence_level distribution:")
    log(t["confidence_level"].value_counts().head(6).to_string())

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "27_infra_probe.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/27_infra_probe.txt" % RESULTS)
    log("INFRA_PROBE_DONE")


if __name__ == "__main__":
    main()
