#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_dates.py -- establish the *real* temporal coverage of every staged
dataset, plus its usable join keys.

Why this is a separate step: the sprint plan asserts coverage windows (e.g. that
the Gwern archive spans 2016-2018) that decide which natural experiment is even
identifiable. Those assertions must be checked against the bytes on disk before
any design is committed to, because a design built on an assumed window produces
confident, well-formed, and meaningless results.

Output is a plain-text report written to
/root/cis/results/00_date_audit.txt and echoed to stdout.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import glob
import json
import os
import re
import sys

DATA = "/root/cis/data"
OUT = "/root/cis/results/00_date_audit.txt"
_LINES = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _LINES.append(s)


DATE_PATTERNS = [
    ("%Y-%m-%d %H:%M:%S", r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"),
    ("%Y-%m-%d", r"^\d{4}-\d{2}-\d{2}"),
    ("%B %d, %Y", r"^[A-Z][a-z]+ \d{1,2}, \d{4}"),
    ("%b %d, %Y", r"^[A-Z][a-z]{2} \d{1,2}, \d{4}"),
]


def parse_date(s):
    s = (s or "").strip().strip('"')
    for fmt, pat in DATE_PATTERNS:
        if re.match(pat, s):
            try:
                return dt.datetime.strptime(s[:len(dt.datetime.now().strftime(fmt))], fmt).date()
            except Exception:  # noqa: BLE001
                try:
                    return dt.datetime.strptime(s, fmt).date()
                except Exception:  # noqa: BLE001
                    pass
    return None


def months_between(d0, d1):
    return (d1.year - d0.year) * 12 + (d1.month - d0.month) + 1


def coverage(name, dates, extra=""):
    ds = [d for d in dates if d]
    if not ds:
        log("  %-34s NO DATES PARSED %s" % (name, extra))
        return None
    lo, hi = min(ds), max(ds)
    log("  %-34s %s .. %s  (%d months, n=%d) %s"
        % (name, lo, hi, months_between(lo, hi), len(ds), extra))
    monthly = collections.Counter(d.strftime("%Y-%m") for d in ds)
    top = monthly.most_common()
    log("      busiest months: %s" % ", ".join("%s=%d" % (m, c) for m, c in top[:5]))
    log("      quietest months: %s" % ", ".join("%s=%d" % (m, c) for m, c in sorted(top)[:5]))
    return lo, hi, monthly


def head_csv(path, n=2):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh)
        rows = []
        for i, r in enumerate(rd):
            rows.append(r)
            if i >= n:
                break
        return rows


def main():
    log("=" * 78)
    log("DATE / COVERAGE AUDIT   %s" % dt.datetime.now().isoformat(timespec="seconds"))
    log("=" * 78)

    # ---------------- AlphaBay (social layer, the only long panel) ----------------
    ab = os.path.join(DATA, "extracted/alphabay_2017-01-28/20170128-alphabay/processed-csv")
    log("\n[A] AlphaBay 2017-01-28 scrape")
    fb = os.path.join(ab, "all_feedback.csv")
    if os.path.exists(fb):
        rows = head_csv(fb, 1)
        log("  header: %s" % rows[0])
        dates, rating_c, item_c = [], collections.Counter(), collections.Counter()
        vendors = collections.Counter()
        n = 0
        with open(fb, "r", encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            next(rd, None)
            for r in rd:
                if len(r) < 5:
                    continue
                n += 1
                d = parse_date(r[0])
                if d:
                    dates.append(d)
                rating_c[r[3].strip().lower()] += 1
                item_c[r[4].strip()] += 1
        log("  feedback rows: %d   distinct items: %d" % (n, len(item_c)))
        log("  rating values: %s" % dict(rating_c.most_common(6)))
        coverage("alphabay feedback dates", dates)
    al = os.path.join(ab, "active listings.csv")
    if os.path.exists(al):
        rows = head_csv(al, 1)
        log("  listings header (%d cols): %s" % (len(rows[0]), rows[0][:14]))
        log("  listings row0: %s" % [c[:40] for c in rows[1][:14]])
        vc, cc = collections.Counter(), collections.Counter()
        n = 0
        with open(al, "r", encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            hdr = next(rd, [])
            iv = 0
            for i, h in enumerate(hdr):
                hl = h.strip().lower()
                if "vendor" in hl or "seller" in hl:
                    iv = i
                if "categor" in hl:
                    cc_i = i
            rd2 = csv.reader(open(al, "r", encoding="utf-8", errors="replace", newline=""))
            next(rd2, None)
            for r in rd2:
                n += 1
                if iv < len(r):
                    vc[r[iv].strip()] += 1
                try:
                    if cc_i < len(r):
                        cc[r[cc_i].strip()] += 1
                except NameError:
                    pass
        log("  listings rows: %d   distinct vendors: %d   distinct categories: %d"
            % (n, len(vc), len(cc)))
        log("  top categories: %s" % ", ".join("%s(%d)" % (k[:28], v) for k, v in cc.most_common(8)))

    # ---------------- Agora ----------------
    log("\n[B] Agora 2014-2015")
    ag = glob.glob(os.path.join(DATA, "extracted/agora_2014_2015/*.csv"))
    if ag:
        rows = head_csv(ag[0], 1)
        log("  header: %s" % rows[0])
        vc, cc = collections.Counter(), collections.Counter()
        n = 0
        with open(ag[0], "r", encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            next(rd, None)
            for r in rd:
                n += 1
                if len(r) > 1:
                    vc[r[0].strip()] += 1
                    cc[r[1].strip()] += 1
        log("  rows: %d  distinct vendors: %d  distinct categories: %d"
            % (n, len(vc), len(cc)))
        log("  top categories: %s" % ", ".join("%s(%d)" % (k[:28], v) for k, v in cc.most_common(8)))
        log("  NOTE: no date column -> cross-sectional only, cannot support a pre/post window.")

    # ---------------- Hansa / Valhalla ----------------
    log("\n[C] Hansa + Valhalla dumps (2016)")
    for p in sorted(glob.glob(os.path.join(DATA, "extracted/hansa_valhalla/**/*.csv"), recursive=True)):
        rows = head_csv(p, 1)
        log("  %-52s rows_hdr=%s" % (os.path.basename(p), rows[0][:5]))
        if rows[1]:
            log("      row0: %s" % [c[:60] for c in rows[1][:7]])
        dates = []
        with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
            for r in csv.reader(fh):
                if r:
                    d = parse_date(r[0])
                    if d:
                        dates.append(d)
        coverage("   " + os.path.basename(p)[:30], dates)

    # ---------------- Kilos ----------------
    log("\n[D] Kilos multi-market reviews")
    for p in glob.glob(os.path.join(DATA, "extracted/kilos_6dnms_reviews/*.csv")):
        rows = head_csv(p, 1)
        log("  header: %s" % rows[0])
        markets, vendors = collections.Counter(), collections.Counter()
        n = 0
        with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            next(rd, None)
            for r in rd:
                n += 1
                if len(r) > 1:
                    markets[r[0].strip()] += 1
                    vendors[r[1].strip()] += 1
        log("  rows: %d  markets: %d  vendors: %d" % (n, len(markets), len(vendors)))
        log("  markets: %s" % dict(markets.most_common()))

    # ---------------- druglisting ----------------
    log("\n[E] Kaggle drug listing dataset (multi-market)")
    for p in glob.glob(os.path.join(DATA, "extracted/druglistingdataset/*.csv")):
        rows = head_csv(p, 1)
        log("  header: %s" % rows[0])
        src, sellers = collections.Counter(), collections.Counter()
        n = 0
        with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            hdr = next(rd, [])
            try:
                si = [h.strip().lower() for h in hdr].index("source")
                se = [h.strip().lower() for h in hdr].index("seller")
            except ValueError:
                si = se = -1
            for r in rd:
                n += 1
                if si >= 0 and si < len(r):
                    src[r[si].strip()] += 1
                if se >= 0 and se < len(r):
                    sellers[r[se].strip()] += 1
        log("  rows: %d  distinct source markets: %d  distinct sellers: %d"
            % (n, len(src), len(sellers)))
        log("  sources: %s" % dict(src.most_common(12)))

    # ---------------- ThreatFox ----------------
    log("\n[F] ThreatFox IOC dump (infrastructure layer)")
    for p in glob.glob(os.path.join(DATA, "_recon/abusech/threatfox_full__*.csv")):
        log("  file: %s (%d bytes)" % (os.path.basename(p), os.path.getsize(p)))
        fs, ls, ttypes, mw = [], [], collections.Counter(), collections.Counter()
        n = 0
        with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            for r in rd:
                if not r or r[0].startswith("#") or not r[0].strip():
                    continue
                n += 1
                d = parse_date(r[0])
                if d:
                    fs.append(d)
                if len(r) > 8:
                    d2 = parse_date(r[8])
                    if d2:
                        ls.append(d2)
                if len(r) > 4:
                    ttypes[r[4].strip()] += 1
                if len(r) > 5:
                    mw[r[5].strip()] += 1
        log("  rows: %d" % n)
        coverage("threatfox first_seen", fs)
        coverage("threatfox last_seen ", ls)
        log("  threat_type: %s" % dict(ttypes.most_common(8)))
        log("  top malware: %s" % dict(mw.most_common(10)))

    # ---------------- URLhaus ----------------
    log("\n[G] URLhaus URL dump (infrastructure layer)")
    for p in glob.glob(os.path.join(DATA, "_recon/abusech/urlhaus_full__*.txt")):
        log("  file: %s (%d bytes)" % (os.path.basename(p), os.path.getsize(p)))
        added, online, status, threat = [], [], collections.Counter(), collections.Counter()
        n = 0
        with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            for r in rd:
                if not r or r[0].startswith("#") or not r[0].strip():
                    continue
                n += 1
                if len(r) > 1:
                    d = parse_date(r[1])
                    if d:
                        added.append(d)
                if len(r) > 4:
                    d2 = parse_date(r[4])
                    if d2:
                        online.append(d2)
                if len(r) > 3:
                    status[r[3].strip()] += 1
                if len(r) > 5:
                    threat[r[5].strip()] += 1
        log("  rows: %d" % n)
        coverage("urlhaus date_added", added)
        coverage("urlhaus last_online", online)
        log("  url_status: %s" % dict(status.most_common(6)))
        log("  threat: %s" % dict(threat.most_common(6)))

    # ---------------- Elliptic++ ----------------
    log("\n[H] Elliptic++ (financial layer)")
    ell = os.path.join(DATA, "EllipticPlusPlus-main")
    for p in sorted(glob.glob(os.path.join(ell, "**", "*.csv"), recursive=True)):
        if os.path.getsize(p) < 5000:
            continue
        rows = head_csv(p, 1)
        log("  %-56s %10d B" % (os.path.relpath(p, ell)[:56], os.path.getsize(p)))
        log("      header: %s" % (", ".join(rows[0][:12])))
        if len(rows) > 1:
            log("      row0  : %s" % (", ".join(rows[1][:12])[:160]))
        if "txs_classes" in p:
            c = collections.Counter()
            with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
                rd = csv.reader(fh); next(rd, None)
                for r in rd:
                    if len(r) > 1:
                        c[r[1].strip()] += 1
            log("      classes: %s" % dict(c.most_common()))
        if "txs_features" in p:
            ts = collections.Counter()
            with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
                rd = csv.reader(fh); next(rd, None)
                for r in rd:
                    if len(r) > 1:
                        ts[r[1].strip()] += 1
            ks = sorted(ts, key=lambda x: int(x) if x.isdigit() else 0)
            log("      time steps: %d..%d (%d distinct), n=%d"
                % (int(ks[0]), int(ks[-1]), len(ks), sum(ts.values())) if ks else "      no time steps")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(_LINES) + "\n")
    log("\nwrote %s" % OUT)


if __name__ == "__main__":
    sys.exit(main())
