#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""02_probe_semantics.py -- determine what three columns actually mean before
any experiment reads them.

Three warnings came out of stage 1. Each is the kind that produces a confident,
well-formed, wrong result if it is carried into a model unchecked:

  1. ThreatFox: 14,649 rows have a NON-EMPTY `last_seen_utc` that does not parse
     as a date. If those are column-shifted rows, then their `threat_type`,
     `ioc_type` etc. are shifted too, and any count over those columns is wrong.
  2. URLhaus: `last_online` spans only 2026-06-25 .. 2026-09-23 while `date_added`
     spans 2018-2026. If last_online is clamped to a rolling window, then
     `last_online - date_added` is NOT a time-to-takedown and E0 must not report
     it as one.
  3. Hansa: the unparsed values in the date column are `"9 days"`, `"Next Day"`,
     `"Not specified"`, `"m***9"` -- i.e. shipping text and vendor names. So the
     column is not uniformly a timestamp.

The question in each case is settled by looking at the raw field structure, not
by assuming which reading is convenient.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import glob
import os
import re
import sys

import pandas as pd

csv.field_size_limit(1 << 24)
DATA = "/root/cis/data"


def sep(t):
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


# ---------------------------------------------------------------- ThreatFox
sep("1. ThreatFox -- is the field count uniform, or are rows shifted?")
p = sorted(glob.glob(os.path.join(DATA, "_recon/abusech/threatfox_full__*.csv")))[0]
header = None
ncols = collections.Counter()
shifted_examples = []
unparsed_examples = []
data_rows = 0
with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
    for line in fh:
        if line.startswith("#") or not line.strip():
            continue
        data_rows += 1
        try:
            fields = next(csv.reader([line]))
        except Exception:  # noqa: BLE001
            fields = []
        ncols[len(fields)] += 1
        if len(fields) != 15 and len(shifted_examples) < 4:
            shifted_examples.append(fields[:8])
        if len(fields) == 15 and len(unparsed_examples) < 4:
            ls = fields[8].strip().strip('"')
            if ls and not re.match(r"^\d{4}-\d{2}-\d{2}", ls):
                unparsed_examples.append((ls[:40], fields[3][:24], fields[4][:24]))
print("  data rows: %d" % data_rows)
print("  field-count histogram: %s" % dict(ncols.most_common(8)))
print("  examples of rows with != 15 fields:")
for e in shifted_examples:
    print("     %s" % [str(x)[:34] for x in e])
print("  examples where `last_seen_utc` is non-empty but not a date:")
for e in unparsed_examples:
    print("     last_seen=%r  ioc_type=%r  threat_type=%r" % e)

# Re-read with csv so quoting is honoured, and count where the parsed cell is
# non-empty yet unparseable -- this distinguishes shift (other columns also look
# wrong) from a genuinely different date format (other columns look fine).
with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
    lines = [ln for ln in fh if not ln.startswith("#") and ln.strip()]
rd = csv.reader(lines)
bad = []
for r in rd:
    if len(r) != 15:
        continue
    ls = r[8].strip().strip('"')
    if ls and not re.match(r"^\d{4}-\d{2}-\d{2}", ls):
        bad.append((ls, r[3], r[4]))
print("  csv-parsed non-empty unparseable last_seen: %d" % len(bad))
print("  their distinct shapes: %s"
      % dict(collections.Counter(re.sub(r"\d", "9", b[0][:20]) for b in bad).most_common(6)))
print("  their ioc_type values: %s"
      % dict(collections.Counter(b[1] for b in bad).most_common(6)))
print("  their threat_type values: %s"
      % dict(collections.Counter(b[2] for b in bad).most_common(6)))

# ---------------------------------------------------------------- URLhaus
sep("2. URLhaus -- is `last_online` a real event time or a rolling-window clamp?")
qp = sorted(glob.glob(os.path.join(DATA, "_recon/abusech/urlhaus_full__*.txt")))[0]
df = pd.read_parquet("/root/cis/work/ioc_urlhaus.parquet")
df["year_added"] = pd.to_datetime(df["date_added"]).dt.year
df["has_lo"] = df["last_online"].notna()
tab = df.groupby("year_added").agg(
    n=("id", "size"), with_last_online=("has_lo", "sum"))
tab["pct_with_lo"] = (100.0 * tab["with_last_online"] / tab["n"]).round(1)
print(tab.to_string())
off = df[df["url_status"].str.lower().eq("offline") & df["has_lo"]].copy()
off["lo_year"] = pd.to_datetime(off["last_online"]).dt.year
print("\n  offline rows: %d ; last_online YEAR distribution: %s"
      % (len(off), dict(off["lo_year"].value_counts().sort_index())))
if len(off):
    off["lag_days"] = (pd.to_datetime(off["last_online"]) -
                       pd.to_datetime(off["date_added"])).dt.days
    print("  lag (last_online - date_added) days: min=%s p25=%s median=%s p75=%s max=%s"
          % tuple(off["lag_days"].quantile(q).round(1)
                  for q in (0.0, 0.25, 0.5, 0.75, 1.0)))
    print("  lag by year_added (median): %s"
          % dict(off.groupby("year_added")["lag_days"].median().round(0)))
    print("  NEGATIVE lags (last_online before date_added): %d"
          % int((off["lag_days"] < 0).sum()))
print("\n  VERDICT INPUT: if last_online is clamped to a recent window, the median")
print("  lag must grow with the age of the row. Compare the by-year medians above.")

# ---------------------------------------------------------------- Hansa
sep("3. Hansa -- what is in column 6, and does the row layout shift?")
hp = None
for r_, _d, fs in os.walk(os.path.join(DATA, "extracted/hansa_valhalla")):
    for f in fs:
        if "reviews" in f:
            hp = os.path.join(r_, f)


def clean(s):
    return (s or "").strip().strip('"').strip()


layout = collections.Counter()
col6_kind = collections.Counter()
col4_kind = collections.Counter()
examples = collections.defaultdict(list)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}")
with open(hp, "r", encoding="utf-8", errors="replace", newline="") as fh:
    for r in csv.reader(fh):
        if len(r) < 7:
            continue
        layout[len(r)] += 1
        c4, c5, c6 = clean(r[4]), clean(r[5]), clean(r[6])
        k6 = "date" if DATE_RE.match(c6) else (
            "same_as_col4" if c6 == c4 else (
                "masked_name" if "*" in c6 else (
                    "text" if c6 else "empty")))
        col6_kind[k6] += 1
        if len(examples[k6]) < 3:
            examples[k6].append((c4[:18], c5[:14], c6[:26]))
        k4 = "duration" if re.match(r"^\d+ (day|days|hour)", c4) else (
            "not_specified" if c4.lower().startswith("not spec") else "other")
        col4_kind[k4] += 1
print("  ncols histogram: %s" % dict(layout.most_common(6)))
print("  column 4 kinds: %s" % dict(col4_kind.most_common(6)))
print("  column 6 kinds: %s" % dict(col6_kind.most_common(8)))
for k, v in examples.items():
    print("   %-14s e.g. col4/col5/col6 = %s" % (k, v))

print("\n  VERDICT INPUT: if 'date' is only ~80%% and the remainder is shipping or")
print("  vendor text in the SAME position, the column is not a date column and the")
print("  apparent span is a selection over a mixed column.")

print("\nPROBE_SEMANTICS_DONE")
