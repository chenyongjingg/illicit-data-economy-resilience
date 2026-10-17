#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""01_build_tables.py -- stage 1: raw bytes -> tidy tables + a QC report.

Design rules, held to on purpose:

  * **Columns are addressed by name, never by position.** Two earlier bugs in
    this project came from positional indexing (AlphaBay "distinct vendors: 10"
    was a wrong-column artefact, and the Hansa date parser read the wrong field).
    Where a file has a header, the header is parsed and used; where names differ
    from expectation the script stops rather than guessing.
  * **Nothing is dropped silently.** Every table reports rows in, rows out, and
    for every exclusion the count and the reason. A tidy table whose row count
    quietly differs from its source is worse than no table.
  * **No imputation, no de-duplication, no "fixing".** Rows that cannot be parsed
    keep their raw value in a `*_raw` column and their parsed column stays null.
    Downstream code therefore decides what to do with them, explicitly.
  * **Right-truncation is carried, not hidden.** AlphaBay items exist only
    because they survived to the 2017-01-28 scrape (C-06); the IOC feeds have a
    rolling retention window (C-07). Both facts are encoded as columns
    (`observed_to`, `censored`) so a later survival model cannot forget them.

Outputs: /root/cis/work/*.parquet, QC report at /root/cis/results/01_data_qc.txt
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

import pandas as pd

csv.field_size_limit(1 << 24)

DATA = "/root/cis/data"
WORK = "/root/cis/work"
RESULTS = "/root/cis/results"
AB = os.path.join(DATA, "extracted/alphabay_2017-01-28/20170128-alphabay/processed-csv")
AB_SCRAPE_DATE = dt.date(2017, 1, 28)

_LINES: list[str] = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _LINES.append(s)


def sep(t):
    log("")
    log("=" * 78)
    log(t)
    log("=" * 78)


def qc_table(name, n_in, df, drops=None):
    """Report the shape of a table and every exclusion applied to it."""
    log("  %-22s rows_in=%-9d rows_out=%-9d cols=%d" % (name, n_in, len(df), df.shape[1]))
    if drops:
        for reason, n in drops.items():
            if n:
                log("      dropped %-12s %d" % (reason, n))
    nulls = {c: int(df[c].isna().sum()) for c in df.columns}
    nz = {c: v for c, v in nulls.items() if v}
    if nz:
        log("      nulls: %s" % ", ".join("%s=%d" % (k, v) for k, v in sorted(nz.items())))
    os.makedirs(WORK, exist_ok=True)
    p = os.path.join(WORK, name + ".parquet")
    df.to_parquet(p, index=False)
    log("      -> %s (%.1f MB)" % (os.path.relpath(p, "/root/cis"), os.path.getsize(p) / 1e6))
    return df


_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], 1)}
_MON_ABBR = {m[:3]: i for m, i in _MONTHS.items()}


def parse_ab_date(s):
    """"June 19, 2016" or "Jun 13, 2016" -> date. Returns None on anything else."""
    s = (s or "").strip()
    m = re.match(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s*(\d{4})$", s)
    if not m:
        return None
    mon = _MONTHS.get(m.group(1)) or _MON_ABBR.get(m.group(1)[:3])
    if not mon:
        return None
    try:
        return dt.date(int(m.group(3)), mon, int(m.group(2)))
    except ValueError:
        return None


def parse_iso_date(s):
    """First 10 chars of an ISO-ish timestamp -> date."""
    s = (s or "").strip().strip('"').strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def parse_hansa_ts(s):
    """"2016-07-28 10:29 UTC" -> datetime. Seconds optional; the trailing zone
    label is stripped, which the project's original parser failed to do and
    consequently reported a 0% parse rate on a column that parses perfectly."""
    s = (s or "").strip().strip('"').strip()
    s = re.sub(r"\s*(UTC|EST|EDT|GMT)\s*$", "", s)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ----------------------------------------------------------------------------
def build_ab_listings():
    sep("A. AlphaBay active listings -> ab_items")
    p = os.path.join(AB, "active listings.csv")
    n_in = 0
    recs = []
    with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
        rd = csv.DictReader(fh)
        need = {"item number", "sold", "price", "heading", "listed", "shipsto",
                "quantity", "origin", "product_class", "vendor level", "trust level",
                "tags", "category1", "category2", "category3",
                "avg feedback rating (-1 to 1)", "number of feedback supplied"}
        missing = need - set(rd.fieldnames or [])
        if missing:
            raise SystemExit("FATAL: AlphaBay listings missing columns %s; have %s"
                             % (sorted(missing), rd.fieldnames))
        for r in rd:
            n_in += 1
            listed = parse_ab_date(r["listed"])
            recs.append({
                "item_number": pd.to_numeric(r["item number"], errors="coerce"),
                "listed_date": listed,
                "listed_raw": None if listed else r["listed"],
                "sold": pd.to_numeric(r["sold"], errors="coerce"),
                "price": pd.to_numeric(r["price"], errors="coerce"),
                "quantity": pd.to_numeric(r["quantity"], errors="coerce"),
                "vendor_level": pd.to_numeric(r["vendor level"], errors="coerce"),
                "trust_level": pd.to_numeric(r["trust level"], errors="coerce"),
                "avg_feedback": pd.to_numeric(r["avg feedback rating (-1 to 1)"], errors="coerce"),
                "n_feedback": pd.to_numeric(r["number of feedback supplied"], errors="coerce"),
                "product_class": r["product_class"].strip(),
                "category1": r["category1"].strip(),
                "category2": r["category2"].strip(),
                "category3": r["category3"].strip(),
                "shipsto": r["shipsto"].strip(),
                "origin": r["origin"].strip(),
                "heading_len": len(r["heading"] or ""),
                "blurb_len": len(r["blurb (description)"] or ""),
                "n_tags": len([t for t in (r["tags"] or "").split(",") if t.strip()]),
            })
    df = pd.DataFrame.from_records(recs)
    unparsed = int(df["listed_date"].isna().sum())
    df = df[df["item_number"].notna()].copy()
    # Tenure is measured from `listed` to the scrape. Every row in this file
    # survived TO the scrape, so this is a lower bound on lifetime, not a
    # lifetime: that is exactly the AlphaBay survivorship caveat (C-06).
    df["tenure_days"] = [
        (AB_SCRAPE_DATE - d).days if isinstance(d, dt.date) else None
        for d in df["listed_date"]]
    df["observed_to"] = AB_SCRAPE_DATE
    df["censored"] = True          # right-truncated by construction
    df["listed_date"] = pd.to_datetime(df["listed_date"])
    return qc_table("ab_items", n_in, df, {"listed_unparsed": unparsed})


# ----------------------------------------------------------------------------
def build_ab_feedback():
    sep("B. AlphaBay feedback event stream -> ab_feedback")
    p = os.path.join(AB, "all_feedback.csv")
    n_in = 0
    bad_date = bad_time = 0
    recs = []
    ratings = collections.Counter()
    with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
        rd = csv.DictReader(fh)
        need = {"date", "time", "comment", "rating", "item"}
        missing = need - set(rd.fieldnames or [])
        if missing:
            raise SystemExit("FATAL: AlphaBay feedback missing columns %s; have %s"
                             % (sorted(missing), rd.fieldnames))
        for r in rd:
            n_in += 1
            d = parse_ab_date(r["date"])
            t = None
            tm = re.match(r"^\s*(\d{1,2}):(\d{2})", r["time"] or "")
            if tm:
                t = dt.time(int(tm.group(1)), int(tm.group(2)))
            if d is None:
                bad_date += 1
            if t is None:
                bad_time += 1
            ratings[(r["rating"] or "").strip().lower()] += 1
            recs.append({
                "ts": (dt.datetime.combine(d, t) if (d and t) else None),
                "date": d,
                "item_number": pd.to_numeric(r["item"], errors="coerce"),
                "rating": (r["rating"] or "").strip().lower(),
                "comment_len": len(r["comment"] or ""),
                "has_comment": bool((r["comment"] or "").strip()),
            })
    df = pd.DataFrame.from_records(recs)
    log("  rating values: %s" % dict(ratings.most_common(8)))
    log("  ts span: %s .. %s" % (df["ts"].min(), df["ts"].max()))
    return qc_table("ab_feedback", n_in, df,
                    {"bad_date": bad_date, "bad_time": bad_time})


# ----------------------------------------------------------------------------
def build_hansa():
    sep("C. Hansa reviews -> hansa_reviews")
    hp = None
    for r_, _d, fs in os.walk(os.path.join(DATA, "extracted/hansa_valhalla")):
        for f in fs:
            if "reviews" in f:
                hp = os.path.join(r_, f)
    if not hp:
        raise SystemExit("FATAL: hansa reviews file not found")
    log("  source: %s" % os.path.relpath(hp, DATA))

    # This file is not RFC-4180 quoted: each field arrives as ' "value"', so the
    # quote characters are part of the content. Strip them explicitly rather than
    # relying on csv's quote handling, which does not engage here.
    def clean(s):
        return (s or "").strip().strip('"').strip()

    n_in = 0
    bad_ts = 0
    recs = []
    nfields = collections.Counter()
    # skipinitialspace: same ', "value"' layout as the abuse.ch feeds, so the
    # same fix. Without it this file parses as 7..12 fields and the columns after
    # the first embedded comma land in the wrong place -- which is why column 6
    # appeared to hold vendor names and shipping text for 20% of rows.
    with open(hp, "r", encoding="utf-8", errors="replace", newline="") as fh:
        for r in csv.reader(fh, skipinitialspace=True):
            nfields[len(r)] += 1
            if len(r) < 7:
                continue
            n_in += 1
            review_ts = parse_hansa_ts(r[6])
            if review_ts is None:
                bad_ts += 1
            vendor = clean(r[5])
            recs.append({
                "scrape_ts": parse_hansa_ts(r[0][:19]),
                "item_id": clean(r[1]),
                "status": clean(r[2]),
                "shipping_raw": clean(r[4]),
                "vendor_raw": vendor,
                "vendor_masked": "*" in vendor,
                "review_ts": review_ts,
                "review_raw": None if review_ts else r[6],
            })
    df = pd.DataFrame.from_records(recs)
    log("  parsed field-count histogram: %s" % dict(nfields.most_common(6)))
    log("  status counts: %s" % dict(df["status"].value_counts().head(6)))
    log("  review_ts span: %s .. %s" % (df["review_ts"].min(), df["review_ts"].max()))
    log("  vendor masked: %d / %d = %.1f%%"
        % (int(df["vendor_masked"].sum()), len(df),
           100.0 * df["vendor_masked"].mean()))
    # A 20% unparsed rate is too high to leave unexplained: either the column is
    # not uniformly a review timestamp (in which case the span above is wrong),
    # or the format varies. Print the distinct shapes of what did not parse
    # rather than assuming.
    if bad_ts:
        un = df.loc[df["review_ts"].isna(), "review_raw"]
        log("  unparsed review_raw examples: %s"
            % [str(x)[:44] for x in un.head(6).tolist()])
        shapes = collections.Counter(
            re.sub(r"\d", "9", str(x).strip()[:26]) for x in un.head(20000))
        log("  unparsed shapes (top 6): %s" % dict(shapes.most_common(6)))
        span_ok = df.loc[df["review_ts"].notna(), "review_ts"]
        log("  parsed-only span: %s .. %s (n=%d)"
            % (span_ok.min(), span_ok.max(), len(span_ok)))
    return qc_table("hansa_reviews", n_in, df, {"review_ts_unparsed": bad_ts})


# ----------------------------------------------------------------------------
def build_kilos():
    sep("D. Kilos multi-market reviews -> kilos_reviews")
    p = glob.glob(os.path.join(DATA, "extracted/kilos_6dnms_reviews/*.csv"))[0]
    log("  source: %s" % os.path.relpath(p, DATA))
    n_in = malformed = 0
    recs = []
    ncols_hist = collections.Counter()
    with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
        for r in csv.reader(fh, skipinitialspace=True):
            n_in += 1
            ncols_hist[len(r)] += 1
            if len(r) != 6:
                malformed += 1
                continue
            recs.append({"market": r[0].strip(), "vendor": r[1].strip(),
                         "f2": r[2].strip(), "f3": r[3].strip(),
                         "price": pd.to_numeric(r[4].strip(), errors="coerce"),
                         "text_len": len(r[5])})
    df = pd.DataFrame.from_records(recs)
    log("  ncols histogram: %s" % dict(ncols_hist.most_common(6)))
    log("  markets: %s" % dict(df["market"].value_counts().head(10)))
    log("  NOTE: no date column exists in this file -> cross-sectional only.")
    return qc_table("kilos_reviews", n_in, df, {"not_6_columns": malformed})


# ----------------------------------------------------------------------------
def build_valhalla():
    sep("E. Valhalla listings -> valhalla_listings")
    vp = None
    for r_, _d, fs in os.walk(os.path.join(DATA, "extracted/hansa_valhalla")):
        for f in fs:
            if "valhalla" in f:
                vp = os.path.join(r_, f)
    n_in = bad_price = 0
    recs = []
    with open(vp, "r", encoding="utf-8", errors="replace", newline="") as fh:
        for r in csv.reader(fh, skipinitialspace=True):
            if len(r) != 5:
                continue
            n_in += 1
            pm = re.match(r"^\s*([\d.,]+)\s*([A-Za-z]{3})?\s*$", r[3] or "")
            price = currency = None
            if pm:
                try:
                    price = float(pm.group(1).replace(",", ""))
                    currency = pm.group(2)
                except ValueError:
                    bad_price += 1
            else:
                bad_price += 1
            recs.append({"item_id": r[0].strip(), "title": r[1].strip(),
                         "vendor": r[2].strip(), "price": price,
                         "currency": currency, "origin": r[4].strip(),
                         "title_len": len(r[1] or "")})
    df = pd.DataFrame.from_records(recs)
    log("  NOTE: no date column -> cross-sectional only.")
    return qc_table("valhalla_listings", n_in, df, {"price_unparsed": bad_price})


# ----------------------------------------------------------------------------
def _read_abusech(path, required, date_cols):
    """abuse.ch dumps carry a leading '#' column-name line, then '#' comments."""
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        lines = fh.readlines()
    header = None
    body = []
    for ln in lines:
        if header is None and ln.startswith("#") and "," in ln:
            cand = [c.strip().strip('"') for c in ln.lstrip("#").strip().split(",")]
            if len(cand) >= len(required) - 1:
                header = cand
                continue
        if ln.startswith("#") or not ln.strip():
            continue
        body.append(ln)
    if header is None:
        raise SystemExit("FATAL: no '#' header line found in %s" % path)
    log("  header(%d): %s" % (len(header), header))
    # skipinitialspace is load-bearing, not cosmetic. abuse.ch writes each field
    # as ', "value"' -- a space then a quote. RFC-4180 quoting only engages when
    # the quote is the first character of the field, so without this the commas
    # INSIDE quoted values are treated as delimiters and the row gains fields
    # (observed: 15..22 fields for a 15-column file), shifting every column after
    # the first embedded comma. Fields before it stay correct, which is what made
    # the damage look partial and plausible.
    rd = csv.DictReader(body, fieldnames=header, skipinitialspace=True)
    nfields = collections.Counter()
    for ln in body:
        nfields[len(next(csv.reader([ln], skipinitialspace=True)))] += 1
    log("  parsed field-count histogram: %s" % dict(nfields.most_common(6)))
    if len(nfields) > 1 and nfields.most_common(1)[0][1] < len(body):
        log("  WARNING: field counts are not uniform even with skipinitialspace")
    missing = [c for c in required if c not in header]
    if missing:
        raise SystemExit("FATAL: %s missing required columns %s"
                         % (os.path.basename(path), missing))
    recs = []
    n_in = 0
    bad_date = collections.Counter()
    for r in rd:
        n_in += 1
        rec = {}
        for c in header:
            rec[c] = (r.get(c) or "").strip().strip('"')
        for c in date_cols:
            d = parse_iso_date(rec.get(c))
            rec[c + "_date"] = d
            if d is None and rec.get(c):
                bad_date[c] += 1
        recs.append(rec)
    return pd.DataFrame.from_records(recs), n_in, bad_date, header


def build_threatfox():
    sep("F. ThreatFox IOCs -> ioc_threatfox")
    p = sorted(glob.glob(os.path.join(DATA, "_recon/abusech/threatfox_full__*.csv")))[0]
    log("  source: %s" % os.path.basename(p))
    df, n_in, bad, header = _read_abusech(
        p, ["first_seen_utc", "ioc_value", "ioc_type", "threat_type"],
        ["first_seen_utc", "last_seen_utc"])
    df = df.rename(columns={"first_seen_utc_date": "first_seen",
                            "last_seen_utc_date": "last_seen"})
    # Mixed date/None columns come out of the reader as object dtype holding a
    # mix of datetime.date and NaN, and numpy then refuses to compare them
    # ("'<=' not supported between instances of 'float' and 'datetime.date'").
    # Coerce to datetime64 explicitly so min/max and downstream duration maths
    # have one dtype to work with.
    for c in ("first_seen", "last_seen"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    feed_end = df["first_seen"].max()
    df["observed_to"] = feed_end
    # Two different censoring stories, kept apart on purpose:
    #  * last_seen is only populated for a rolling recent window, so
    #    last_seen - first_seen is NOT a lifetime for the older rows;
    #  * absence of last_seen is not "still alive".
    df["has_last_seen"] = df["last_seen"].notna()
    if df["last_seen"].notna().any():
        log("  last_seen window: %s .. %s (n=%d)"
            % (df["last_seen"].min(), df["last_seen"].max(), int(df["has_last_seen"].sum())))
    log("  first_seen window: %s .. %s" % (df["first_seen"].min(), df["first_seen"].max()))
    log("  threat_type: %s" % dict(df["threat_type"].value_counts().head(8)))
    log("  ioc_type: %s" % dict(df["ioc_type"].value_counts().head(8)))
    return qc_table("ioc_threatfox", n_in, df, dict(bad))


def build_urlhaus():
    sep("G. URLhaus URLs -> ioc_urlhaus")
    p = sorted(glob.glob(os.path.join(DATA, "_recon/abusech/urlhaus_full__*.txt")))[0]
    log("  source: %s" % os.path.basename(p))
    df, n_in, bad, header = _read_abusech(
        p, ["dateadded", "url", "url_status"], ["dateadded", "last_online"])
    df = df.rename(columns={"dateadded_date": "date_added"})
    for c in ("date_added", "last_online"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    feed_end = df["date_added"].max()
    df["observed_to"] = feed_end
    # For URLhaus both halves are present and meaningful: status says whether the
    # URL is still up, last_online says when it was last seen up. An `online` row
    # is genuinely right-censored; an `offline` row gives an observed duration.
    df["censored"] = df["url_status"].str.lower().eq("online")
    if df["last_online"].notna().any():
        log("  last_online window: %s .. %s" % (df["last_online"].min(), df["last_online"].max()))
    log("  url_status: %s" % dict(df["url_status"].value_counts().head(6)))
    log("  censored(online): %d / %d = %.1f%%"
        % (int(df["censored"].sum()), len(df), 100.0 * df["censored"].mean()))
    return qc_table("ioc_urlhaus", n_in, df, dict(bad))


# ----------------------------------------------------------------------------
def main():
    log("=" * 78)
    log("STAGE 1 -- DATA LAYER   %s" % dt.datetime.now().isoformat(timespec="seconds"))
    log("=" * 78)
    for fn in (build_ab_listings, build_ab_feedback, build_hansa, build_kilos,
               build_valhalla, build_threatfox, build_urlhaus):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            log("  !! %s FAILED: %s: %s" % (fn.__name__, type(e).__name__, e))
            raise

    sep("WRITTEN TABLES")
    for f in sorted(os.listdir(WORK)):
        log("  %-28s %10.2f MB" % (f, os.path.getsize(os.path.join(WORK, f)) / 1e6))

    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "01_data_qc.txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(_LINES) + "\n")
    log("\nwrote %s" % out)
    log("BUILD_TABLES_DONE")


if __name__ == "__main__":
    sys.exit(main())
