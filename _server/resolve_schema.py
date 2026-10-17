#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resolve_schema.py -- print the *full* column sets and parse characteristics of
the tables whose schema is still unresolved, using only the standard library so
it can run before the conda env exists.

Open questions this answers:
  * AlphaBay `active listings.csv`: which column actually holds the vendor name
    (the earlier audit reported "distinct vendors: 10", which is an artefact of
    picking the wrong column, not a finding), and what is the real spread of the
    per-listing `listed` date?
  * Hansa reviews: is the trailing column a genuine review timestamp, and over
    what range?
  * Kilos: the file has embedded newlines and quote characters -- what is the
    true field structure?
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import os
import re
import sys

csv.field_size_limit(1 << 24)
DATA = "/root/cis/data"
AB = os.path.join(DATA, "extracted/alphabay_2017-01-28/20170128-alphabay/processed-csv")


def sep(t):
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


def parse_date(s):
    s = (s or "").strip().strip('"')
    for fmt, pat in (
        ("%Y-%m-%d %H:%M:%S", r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"),
        ("%Y-%m-%d", r"^\d{4}-\d{2}-\d{2}"),
        ("%B %d, %Y", r"^[A-Z][a-z]+ \d{1,2}, \d{4}"),
        ("%b %d, %Y", r"^[A-Z][a-z]{2} \d{1,2}, \d{4}"),
    ):
        if re.match(pat, s):
            try:
                return dt.datetime.strptime(s, fmt).date()
            except Exception:  # noqa: BLE001
                pass
    return None


sep("AlphaBay active listings.csv -- FULL schema")
p = os.path.join(AB, "active listings.csv")
with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
    rd = csv.reader(fh)
    hdr = next(rd)
    print("n cols = %d" % len(hdr))
    for i, h in enumerate(hdr):
        print("  [%2d] %r" % (i, h))
    print("\n  first 2 data rows:")
    for _ in range(2):
        r = next(rd, None)
        if r:
            for i, c in enumerate(r):
                print("    [%2d] %s" % (i, str(c)[:110].replace("\n", "\\n")))

sep("AlphaBay listings -- per-column distinct counts (sampled over all rows)")
cnt = collections.defaultdict(collections.Counter)
nonempty = collections.Counter()
nrows = 0
listed_dates = []
with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
    rd = csv.reader(fh)
    hdr = next(rd)
    for r in rd:
        nrows += 1
        for i, c in enumerate(r):
            c = c.strip()
            if c:
                nonempty[i] += 1
                if len(cnt[i]) < 400000:
                    cnt[i][c] += 1
        # look for a date-looking column
        for i, c in enumerate(r):
            d = parse_date(c)
            if d and "listed" in hdr[i].lower():
                listed_dates.append(d)
print("  rows = %d" % nrows)
for i, h in enumerate(hdr):
    ex = ", ".join(repr(k)[:34] for k, _ in cnt[i].most_common(3))
    print("  [%2d] %-22s distinct~%-7d nonempty=%-7d eg: %s"
          % (i, h[:22], len(cnt[i]), nonempty[i], ex[:100]))
if listed_dates:
    print("\n  `listed` date range: %s .. %s  (n=%d)" % (min(listed_dates), max(listed_dates), len(listed_dates)))
    mo = collections.Counter(d.strftime("%Y-%m") for d in listed_dates)
    print("  listed by month (first 30): %s" % sorted(mo.items())[:30])

sep("Hansa reviews -- structure and the trailing date column")
hp = None
for r, _d, fs in os.walk(os.path.join(DATA, "extracted/hansa_valhalla")):
    for f in fs:
        if "reviews" in f:
            hp = os.path.join(r, f)
if hp:
    with open(hp, "r", encoding="utf-8", errors="replace", newline="") as fh:
        rd = csv.reader(fh)
        rows = [next(rd, None) for _ in range(4)]
    print("  file: %s" % hp)
    for r in rows:
        if r:
            print("   ncols=%d  %s" % (len(r), [str(c)[:46] for c in r]))
    dts = collections.Counter()
    st = collections.Counter()
    n = 0
    with open(hp, "r", encoding="utf-8", errors="replace", newline="") as fh:
        for r in csv.reader(fh):
            if not r:
                continue
            n += 1
            for c in r[1:]:
                d = parse_date(c)
                if d:
                    dts[c.strip()] += 1
            if len(r) > 2:
                st[r[2].strip()] += 1
    print("  rows=%d" % n)
    print("  status values: %s" % dict(st.most_common(8)))
    print("  distinct date-like values found: %d" % len(dts))
    if dts:
        print("  date range: %s .. %s" % (min(dts), max(dts)))
        print("  sample dates: %s" % list(dts.most_common(5)))

sep("Kilos -- true structure")
for r_, _d, fs in os.walk(os.path.join(DATA, "extracted/kilos_6dnms_reviews")):
    for f in fs:
        kp = os.path.join(r_, f)
        with open(kp, "r", encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            print("  file: %s" % kp)
            for i in range(4):
                row = next(rd, None)
                if row:
                    print("   ncols=%d  %s" % (len(row), [str(c)[:40] for c in row[:8]]))
        ncols = collections.Counter()
        n = 0
        with open(kp, "r", encoding="utf-8", errors="replace", newline="") as fh:
            for row in csv.reader(fh):
                n += 1
                ncols[len(row)] += 1
        print("  rows=%d  ncols histogram=%s" % (n, dict(ncols.most_common(6))))

sep("Valhalla -- structure")
for r_, _d, fs in os.walk(os.path.join(DATA, "extracted/hansa_valhalla")):
    for f in fs:
        if "valhalla" in f:
            vp = os.path.join(r_, f)
            with open(vp, "r", encoding="utf-8", errors="replace", newline="") as fh:
                rd = csv.reader(fh)
                ncols = collections.Counter()
                n = 0
                for row in rd:
                    n += 1
                    ncols[len(row)] += 1
                    if n <= 3:
                        print("   ncols=%d %s" % (len(row), [str(c)[:44] for c in row]))
                print("  rows=%d ncols histogram=%s" % (n, dict(ncols.most_common(6))))

print("\nDONE")
