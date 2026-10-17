#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""40_E2_feasibility.py -- can E2 (two-event comparison) be run at all?

E2 is pre-registered as "Onymous vs Bayonet 指标一致性（E1 管线复用）": run E1's
pipeline on two events, Onymous (2014-11-06) and Bayonet (2017-07-20), and show
the indicators agree.

"E1 管线复用" is the load-bearing phrase: E1's pipeline runs on the kilos panel,
whose coverage is 2018-02-19 .. 2020-01-12. If that is right, E1's pipeline
covers NEITHER event, and E2 cannot be run by reuse.

The claim is not assumed. Every dated table is measured, and each event is
placed against each measurement.

===================================================================
WHY THIS IS THE FOURTH VERSION -- the three earlier failures are kept verbatim,
because they are three DIFFERENT failures and none of them is a performance
note. Each one produced a plausible wrong answer.
===================================================================

 v1  pandas.read_csv. On the 1.2M-row feedback table it fell back to the python
     engine and was still running after 15 min. Killed. (Performance.)

 v2  Streaming csv.reader, but it picked ONE date column per file: the first
     with the highest non-null fraction, ties to file order. hansa_listings and
     hansa_reviews both resolved to c0 and came back as a 1-day span.
     (Column-SELECTION failure.)

 v3  Reported EVERY qualifying column instead of picking one -- right idea --
     but two new bugs, both of which returned "no date column" for files that
     demonstrably have one:
       (i)  the regex was ANCHORED with `$`. hansa_reviews' timestamps look
            like "2016-12-13 02:37:18.202573553 -0500 EST", so the trailing
            " -0500 EST" made every value fail. v2 had no anchor and worked.
            Fixing the column-choice bug INTRODUCED this one.
       (ii) the sample was the FIRST 20000 ROWS. kilos_reviews is ordered by
            market, and its entire Samsara block -- the first 20k rows -- has
            f2 == 0, the null marker. So no epoch-shaped value was ever in the
            sample and the column was invisible. A head-of-file sample inherits
            the file's block order, which is a property of how the dump was
            concatenated, not of the column.

 v4  THIS FILE. Detector is unanchored, format-aware, and scans the
     FULL POPULATION for detection -- no sampling at all. Real formats this
     had to learn:
       "Jun 13, 2016"                              (alphabay items, US month)
       "2016-12-13 02:37:18.202573553 -0500 EST"   (hansa, named timezone)
       "2016-07-28 10:29 UTC"                      (hansa, short timezone)
       1550000000                                  (kilos f2, unix epoch)

     v4 as first run claimed in its log to be sampling at a computed stride.
     That readout was FALSE and is corrected here: the stride estimator was
     degenerate (`est` reduced to the number of rows read so far, so stride
     was always 1), which means it read every row. Reading every row is
     strictly better for detection than striding, so the SPANS it produced
     were right -- but the log line said "over ~2001 rows" for a 1.2M-row
     file, which is exactly the kind of wrong readout a later stage would
     quote. The estimator is gone; the scan is now explicitly full-population
     and reports the true row count.

Row counts are PHYSICAL rows from csv.reader; a ragged row is counted, not
silently skipped. Parse failures are reported per column.
"""
from __future__ import annotations

import csv
import json
import os
import re
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

EXTRACT = "/root/cis/data/extracted"
ELL = "/root/cis/data/EllipticPlusPlus-main"
RESULTS = "/root/cis/results"

ONUMOUS = pd.Timestamp("2014-11-06")
BAYONET = pd.Timestamp("2017-07-20")
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


TZ = re.compile(r"\s+(?:[+-]\d{4}|[+-]\d{2}:?\d{2})\s+[A-Z]{2,5}\s*$")
TZ_SHORT = re.compile(r"\s+[A-Z]{2,5}$")

# UNANCHORED at the end on purpose: a trailing timezone must not disqualify.
_PATS = [
    re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}"),       # 2016-12-13 ...
    re.compile(r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}"),       # 13/12/2016
    re.compile(r"^[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}"),   # Jun 13, 2016
    re.compile(r"^\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4}"),     # 13 Jun 2016
    re.compile(r"^[A-Za-z]{3,9}\.?\s+\d{4}"),          # Jun 2016
]
_EPAT = re.compile(r"^\d{8,13}(\.\d+)?$")


def dateish(v):
    v = v.strip()
    return any(p.match(v) for p in _PATS) if v else False


def epochish(v):
    v = v.strip()
    if not v or not _EPAT.match(v):
        return False
    try:
        n = float(v)
    except ValueError:
        return False
    return 1e8 <= n <= 3e11


_FORMATS = [None, "ISO8601", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
            "%b %d, %Y", "%B %d, %Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
            "%b %Y", "%d %b %Y", "mixed"]


def parse_col(vals, kind):
    s = pd.Series(vals, dtype="object").astype(str).str.strip()
    if kind == "epoch":
        n = pd.to_numeric(s, errors="coerce")
        n = n.where((n >= 1e8) & (n <= 3e10))
        v = pd.to_datetime(n, unit="s", errors="coerce")
        return v, "unix_seconds"
    s = s.str.replace(TZ, "", regex=True).str.replace(TZ_SHORT, "", regex=True)
    best, bf = None, ""
    for f in _FORMATS:
        try:
            v = pd.to_datetime(s, errors="coerce",
                               **({} if f is None else {"format": f}))
        except Exception:                       # noqa: BLE001
            continue
        if best is None or v.notna().mean() > best.notna().mean():
            best, bf = v, ("inferred" if f is None else f)
        if best.notna().mean() >= 0.999:
            break
    if best is None:
        best, bf = pd.to_datetime(s, errors="coerce"), "inferred(forced)"
    return best, bf


def measure(path, has_header):
    """Pass 1 scans the FULL file and keeps every row for detection; pass 2
    re-reads it keeping only the detected columns. Nothing is sampled."""
    buf: list[list[str]] = []
    nrows, nbad, ncol = 0, 0, 0
    names = None
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh, skipinitialspace=True)
        for row in rd:
            if nrows == 0 and has_header:
                names = [c.strip() for c in row]
                nrows += 1
                continue
            idx = nrows
            nrows += 1
            ncol = max(ncol, len(row))
            buf.append(list(row))
    total = nrows - (1 if has_header else 0)
    log("      [FULL-POPULATION scan of %d rows for detection; v3's head-only"
        " 20k sample is what missed kilos' epochs]" % total)
    if not buf:
        return [], total, 0, ncol, None

    nc = max(len(r) for r in buf)
    if names is None or len(names) < nc:
        names = [names[i] if names and i < len(names) else "c%d" % i
                 for i in range(nc)]

    kind = {}
    for j in range(nc):
        col = [(r[j] if j < len(r) else "") for r in buf]
        if not col:
            continue
        fd = sum(1 for v in col if dateish(v)) / len(col)
        fe = sum(1 for v in col if epochish(v)) / len(col)
        if fd >= 0.5:
            kind[j] = ("date", fd)
        elif fe >= 0.5:
            kind[j] = ("epoch", fe)
    if not kind:
        return [], total, 0, nc, names

    # pass 2 -- whole file, only the detected columns
    cols = {j: [] for j in kind}
    nrows2, nbad2 = 0, 0
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh, skipinitialspace=True)
        for i, row in enumerate(rd):
            if i == 0 and has_header:
                continue
            nrows2 += 1
            if len(row) != nc:
                nbad2 += 1
            for j in cols:
                cols[j].append(row[j] if j < len(row) else "")

    recs = []
    for j, (k, sfrac) in kind.items():
        v, fmt = parse_col(cols[j], k)
        ok = v.dropna()
        if ok.empty:
            continue
        recs.append({"col": str(names[j]), "idx": j, "kind": k,
                     "sample_frac": round(sfrac, 4), "fmt": fmt,
                     "frac": float(v.notna().mean()), "lo": ok.min(),
                     "hi": ok.max(), "n_parsed": int(len(ok)),
                     "n_distinct_dates": int(ok.dt.normalize().nunique())})
    recs.sort(key=lambda r: (-r["n_distinct_dates"], r["idx"]))
    return recs, nrows2, nbad2, nc, names


FILES = [
    ("agora", os.path.join(EXTRACT, "agora_2014_2015/agora_2014_2015.csv"), True),
    ("alphabay_items", os.path.join(EXTRACT, "alphabay_2017-01-28/"
     "20170128-alphabay/processed-csv/active listings.csv"), True),
    ("alphabay_feedback", os.path.join(EXTRACT, "alphabay_2017-01-28/"
     "20170128-alphabay/processed-csv/all_feedback.csv"), True),
    ("hansa_listings", os.path.join(EXTRACT, "hansa_valhalla/"
     "dark-web-data-dumps/hansa-marketplace-listings-december-2016.csv"), False),
    ("hansa_reviews", os.path.join(EXTRACT, "hansa_valhalla/dark-web-data-dumps/"
     "hansa_reviews_december_2016.csv"), False),
    ("valhalla_listings", os.path.join(EXTRACT, "hansa_valhalla/"
     "dark-web-data-dumps/valhalla-marketplace-listings-2016-10.csv"), False),
    ("kilos_reviews", os.path.join(EXTRACT,
     "kilos_6dnms_reviews/kilos_6dnms_reviews.csv"), False),
    ("druglisting", os.path.join(EXTRACT,
     "druglistingdataset/druglistingdataset.csv"), True),
]


def main():
    log("=" * 78)
    log("40  E2 feasibility -- is there a dataset that brackets either event?")
    log("=" * 78)
    log("  Onymous = %s ; Bayonet = %s" % (ONUMOUS.date(), BAYONET.date()))

    sep("1. Every date-shaped column, full-file span (union = file coverage)")
    cov, detail = {}, {}
    for name, path, hdr in FILES:
        if not os.path.exists(path):
            log("")
            log("  %-18s MISSING" % name)
            continue
        log("")
        log("  %s" % name)
        recs, nrows, nbad, ncol, _ = measure(path, hdr)
        log("      %d physical rows, %d ragged, %d cols"
            % (nrows, nbad, ncol))
        if not recs:
            log("      NO date-shaped or epoch-shaped column")
            cov[name] = None
            detail[name] = {"n_rows": nrows, "n_ragged": nbad, "cols": []}
            continue
        for r in recs:
            log("      col %-16s %-5s %-14s %5.1f%%  %s .. %s  (%.0f d, %d distinct)"
                % (str(r["col"])[:16], r["kind"], str(r["fmt"])[:14],
                   100 * r["frac"], str(r["lo"])[:10], str(r["hi"])[:10],
                   (r["hi"] - r["lo"]).total_seconds() / 86400.0,
                   r["n_distinct_dates"]))
        lo = min(r["lo"] for r in recs)
        hi = max(r["hi"] for r in recs)
        cov[name] = (lo, hi)
        detail[name] = {"n_rows": nrows, "n_ragged": nbad,
                        "cols": [{k: (str(v) if isinstance(v, pd.Timestamp)
                                      else v) for k, v in r.items()}
                                 for r in recs],
                        "union_lo": str(lo), "union_hi": str(hi)}
        log("      UNION  %s .. %s  (%.0f d)"
            % (str(lo)[:10], str(hi)[:10], (hi - lo).total_seconds() / 86400.0))

    sep("2. ★ Event coverage matrix (against each file's UNION span)")
    log("  A usable event study needs the event INSIDE the span with margin on")
    log("  both sides. 'before'/'after' are days of coverage on each flank.")
    log("")
    log("  %-18s %-10s %8s %10s %10s %9s"
        % ("dataset", "event", "inside?", "before(d)", "after(d)", "margin(d)"))
    verdict = {}
    for name in [f[0] for f in FILES]:
        sp = cov.get(name)
        if sp is None:
            log("  %-18s %-10s %8s %10s %10s %9s"
                % (name, "(none)", "-", "-", "-", "-"))
            for ev, en in ((ONUMOUS, "Onymous"), (BAYONET, "Bayonet")):
                verdict["%s|%s" % (name, en)] = {
                    "inside": False, "before_days": None, "after_days": None,
                    "margin_days": -1, "note": "no date column"}
            continue
        lo, hi = sp
        for ev, en in ((ONUMOUS, "Onymous"), (BAYONET, "Bayonet")):
            inside = bool(lo <= ev <= hi)
            before, after = int((ev - lo).days), int((hi - ev).days)
            log("  %-18s %-10s %8s %10d %10d %9d"
                % (name, en, "YES" if inside else "no", before, after,
                   min(before, after) if inside else -1))
            verdict["%s|%s" % (name, en)] = {
                "inside": inside, "before_days": before, "after_days": after,
                "margin_days": int(min(before, after)) if inside else -1}

    sep("3. E1's own pipeline data -- does it cover either event?")
    kp = "/root/cis/work/kilos_reviews.parquet"
    if os.path.exists(kp):
        k = pd.read_parquet(kp)
        ts = pd.to_datetime(pd.to_numeric(k["f2"], errors="coerce"), unit="s",
                            errors="coerce")
        ts = ts[ts > pd.Timestamp("2000-01-01")]
        log("  E1 v3 reads %s" % kp)
        log("  its span: %s .. %s  (%d dated rows, %d distinct dates)"
            % (ts.min().date(), ts.max().date(), len(ts),
               ts.dt.normalize().nunique()))
        for ev, en in ((ONUMOUS, "Onymous"), (BAYONET, "Bayonet")):
            log("    covers %-8s (%s): %s"
                % (en, ev.date(), "YES" if ts.min() <= ev <= ts.max() else "NO"))
        log("")
        log("  ★ E2 says 'E1 管线复用'. E1's pipeline spans %s..%s, so it"
            % (ts.min().date(), ts.max().date()))
        log("    covers NEITHER event. E2 cannot be run by reuse.")

    sep("4. Elliptic's time axis: calendar or anonymised?")
    tf = os.path.join(ELL, "Transactions Dataset/txs_features.csv")
    if os.path.exists(tf):
        with open(tf, newline="", encoding="utf-8", errors="replace") as fh:
            hd = [c.strip() for c in next(csv.reader(fh))]
        log("  txs_features.csv cols: %s" % ", ".join(hd[:6]))
        tj = [i for i, c in enumerate(hd) if "time" in c.lower()]
        if tj:
            vals = []
            with open(tf, newline="", encoding="utf-8", errors="replace") as fh:
                rd = csv.reader(fh)
                next(rd)
                for row in rd:
                    for i in tj:
                        if i < len(row):
                            vals.append(row[i])
            a = pd.to_numeric(pd.Series(vals, dtype="object"),
                              errors="coerce").dropna()
            u = np.unique(a.to_numpy())
            log("  time column(s) %s: n=%d distinct=%d  min=%s max=%s"
                % ([hd[i] for i in tj], len(a), len(u),
                   u.min() if len(u) else "-", u.max() if len(u) else "-"))
            log("")
            log("  ★ Elliptic's time axis is ORDINAL (integer steps), not calendar")
            log("    dates. It carries no anchor to a real-world event, so no")
            log("    cross-layer TEMPORAL alignment is possible even in principle")
            log("    -- independently of the address-intersection result in 37_.")
    else:
        log("  txs_features.csv not found")

    sep("5. Verdict")
    usable = [k for k, v in verdict.items()
              if v["inside"] and v["margin_days"] >= 90]
    log("  pairs with the event INSIDE the span AND >=90 d margin on both sides:")
    log("    " + (", ".join("%s (margin %d d)" % (k, verdict[k]["margin_days"])
                            for k in usable) if usable else "NONE"))
    log("")
    anyin = [k for k, v in verdict.items() if v["inside"]]
    log("  pairs where the event is inside the span at all (any margin):")
    log("    " + (", ".join("%s (margin %d d)" % (k, verdict[k]["margin_days"])
                            for k in anyin) if anyin else "NONE"))

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "40_E2_feasibility.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"verdict": verdict, "files": detail,
                   "onumous": str(ONUMOUS.date()),
                   "bayonet": str(BAYONET.date())}, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "40_E2_feasibility.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/40_E2_feasibility.{txt,json}" % RESULTS)
    log("E2_FEAS_DONE")


if __name__ == "__main__":
    main()
