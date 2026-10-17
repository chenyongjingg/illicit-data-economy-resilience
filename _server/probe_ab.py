#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_ab.py -- resolve the last identity questions before the data layer.

Three things must be settled by looking at bytes, because each one decides
whether an experiment unit exists at all:

  1. AlphaBay has no vendor column in `active listings.csv` (18 columns, verified).
     Is vendor identity recoverable from `heading` (many look like
     "TITLE (VENDORNAME)") or from the feedback `comment` text? If not, E4's
     vendor-tenure survival has no unit and must be reframed onto items.
  2. Does the AlphaBay dump ship any other table (a vendor table) that was missed?
  3. Hansa's review dates live in column 6 as "2016-07-28 10:29 UTC" -- no
     seconds, so the project's `parse_date` rejected them and reported
     "distinct date-like values found: 0". Confirm the true parse rate.
  4. Elliptic++ LFS: report each object's size so the resumable fetcher can be
     sized, and state how much of the current partial survived.
"""
from __future__ import annotations

import collections
import csv
import os
import re
import sys

csv.field_size_limit(1 << 24)
DATA = "/root/cis/data"
AB = os.path.join(DATA, "extracted/alphabay_2017-01-28/20170128-alphabay/processed-csv")


def sep(t):
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


sep("1. AlphaBay dump -- every file shipped, not just the two known CSVs")
for r, d, fs in os.walk(os.path.join(DATA, "extracted/alphabay_2017-01-28")):
    for f in sorted(fs):
        p = os.path.join(r, f)
        print("  %10d  %s" % (os.path.getsize(p), os.path.relpath(p, DATA)))

sep("2. AlphaBay feedback -- header and sample, looking for vendor identity")
fb = os.path.join(AB, "all_feedback.csv")
with open(fb, "r", encoding="utf-8", errors="replace", newline="") as fh:
    rd = csv.reader(fh)
    hdr = next(rd)
    print("  header (%d cols): %s" % (len(hdr), hdr))
    for i in range(5):
        r = next(rd, None)
        if r:
            print("   [%d] %s" % (i, [str(c)[:60] for c in r]))

sep("3. Are vendor names recoverable? (a) trailing parenthetical in `heading`")
pat = re.compile(r"\(([^()]{2,32})\)\s*$")
n = hit = 0
vendors = collections.Counter()
examples = []
with open(os.path.join(AB, "active listings.csv"), "r", encoding="utf-8",
          errors="replace", newline="") as fh:
    rd = csv.reader(fh)
    next(rd, None)
    for r in rd:
        n += 1
        if len(r) > 3:
            m = pat.search(r[3])
            if m:
                hit += 1
                vendors[m.group(1).strip()] += 1
                if len(examples) < 5:
                    examples.append(r[3][:70])
print("  listings with a trailing '(NAME)': %d / %d = %.1f%%" % (hit, n, 100.0 * hit / n))
print("  distinct such names: %d" % len(vendors))
print("  most common: %s" % ", ".join("%s(%d)" % (k[:24], v) for k, v in vendors.most_common(12)))
print("  examples: %s" % examples)

sep("3b. (b) does the feedback `comment` field name vendors?")
cm = collections.Counter()
with open(fb, "r", encoding="utf-8", errors="replace", newline="") as fh:
    rd = csv.reader(fh)
    next(rd, None)
    for i, r in enumerate(rd):
        if i >= 3000:
            break
        if len(r) > 2:
            cm[r[2][:70]] += 1
print("  sample comments: %s" % [c for c, _ in cm.most_common(6)])

sep("4. Hansa review-date parse rate with the correct format")
hp = None
for r_, _d, fs in os.walk(os.path.join(DATA, "extracted/hansa_valhalla")):
    for f in fs:
        if "reviews" in f:
            hp = os.path.join(r_, f)
PATTERNS = [(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "%Y-%m-%d %H:%M:%S"),
            (r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}", "%Y-%m-%d %H:%M"),
            (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d")]
import datetime as dt
ok = bad = 0
dates = []
rows = 0
with open(hp, "r", encoding="utf-8", errors="replace", newline="") as fh:
    for r in csv.reader(fh):
        if len(r) < 7:
            continue
        rows += 1
        s = r[6].strip().strip('"').strip()
        for pat_, fmt in PATTERNS:
            if re.match(pat_, s):
                try:
                    dates.append(dt.datetime.strptime(s[:len(fmt) + 6], fmt).date())
                    ok += 1
                except Exception:  # noqa: BLE001
                    bad += 1
                break
        else:
            bad += 1
print("  rows=%d  parsed=%d  unparsed=%d" % (rows, ok, bad))
if dates:
    print("  review date range: %s .. %s" % (min(dates), max(dates)))
    by = collections.Counter(d.strftime("%Y-%m") for d in dates)
    print("  by month (top 12): %s" % ", ".join("%s=%d" % (k, v) for k, v in sorted(by.items())[:12]))
print("  vendor column masking (col 5):")
vm = collections.Counter()
with open(hp, "r", encoding="utf-8", errors="replace", newline="") as fh:
    for r in csv.reader(fh):
        if len(r) >= 6:
            vm[r[5].strip().strip('"')] += 1
masked = sum(v for k, v in vm.items() if "*" in k)
print("    distinct=%d  of which contain '*': %d (%.1f%% of rows)"
      % (len(vm), sum(1 for k in vm if "*" in k),
         100.0 * sum(v for k, v in vm.items() if "*" in k) / max(1, sum(vm.values()))))

sep("5. Elliptic++ LFS object sizes and surviving partial")
ELL = os.path.join(DATA, "EllipticPlusPlus-main")
tot = 0
for r_, _d, fs in os.walk(ELL):
    for f in fs:
        if not f.lower().endswith(".csv"):
            continue
        p = os.path.join(r_, f)
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(300)
        if "git-lfs.github.com/spec/v1" in head:
            size = None
            for line in head.splitlines():
                if line.startswith("size "):
                    size = int(line.split()[1])
            tot += size or 0
            print("  POINTER %10s  %s" % (size, os.path.relpath(p, ELL)))
        else:
            print("  ok      %10d  %s" % (os.path.getsize(p), os.path.relpath(p, ELL)))
print("  total still in LFS: %.1f MB" % (tot / 1e6))
cd = os.path.join(DATA, "lfs_cache")
if os.path.isdir(cd):
    for f in os.listdir(cd):
        print("  cache: %12d  %s" % (os.path.getsize(os.path.join(cd, f)), f))
print("\nPROBE_AB_DONE")
