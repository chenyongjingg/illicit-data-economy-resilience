#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""71 (v2) -- what interval does each issue's number actually cover?

WHY THIS EXISTS
---------------
The p.6 figures are not free-floating totals: each issue prints, inside a
screenshot of the publisher's own search UI, the query that produced the number
-- a `release_time<=` bound, an `录入时间大于等于` / `录入时间小于等于` pair, and
in one case the result count itself (`为您找到6826条匹配结果`, 2025-08, where 6826
IS the issue's second headline figure). So the window is written on the page and
is checkable.

It matters because if the issues do not each cover their own month, then the E9
external series is not a monthly time series and its shape is partly a property
of the publisher's query. That is a statement about the E9 instrument that has
to be made explicitly rather than discovered by a reader later.

WHY v2
------
v1 recognized only the two full word forms and therefore reported `-` for most
issues. It missed 2025-11 entirely, whose bound survives OCR only as the
fragment `于等于：2025-12-01`. A field that is empty nearly everywhere is the
shape of a narrow regex, not the shape of an absence, so v2 widens the forms and
-- the point -- reports a bound it cannot classify into a separate UNCLASSIFIED
bucket instead of dropping it. Unread is reported as unread.

It still refuses to emit when it finds NO bound anywhere, so "nothing found" and
"nothing there" cannot share a return value.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "results")
OCR_DIR = os.path.join(RES, "59_ocr_full_text")
PDF_DIR = os.path.join(ROOT, "data", "external", "dwcon")
OUT = os.path.join(RES, "71_E9_query_windows.json")

PERIODS = ["2025-01", "2025-02", "2025-03", "2025-04",
           "2025-06", "2025-07", "2025-08", "2025-10", "2025-11"]

D = r"(\d{4})-(\d{1,2})-(\d{1,2})"
# Matched against a DESPACED view: CJK typesetting breaks lines inside words, so
# `录入时间小于` and `等于：2025-12-01` can be separated by a space that is not in
# the word (the defect that made 69_ v1 report `-` for four fields).
FORMS = [
    ("upper_op", re.compile(r"(?:release_time)?<=\s*" + D)),
    ("lower_words", re.compile(r"大于等于[:：]?" + D)),
    ("upper_words", re.compile(r"小于等于[:：]?" + D)),
    # Bucket for fragments OCR cut down (e.g. `于等于：2025-12-01`, which is
    # 小于等于 with its first two characters lost). Kept SEPARATE: the sign is
    # not recoverable from the fragment alone, so it must not be guessed at.
    ("UNCLASSIFIED_等于", re.compile(r"等于[:：]" + D)),
]


def despaced(s):
    return re.sub(r"\s+", "", s)


def iso(m):
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return "INVALID(%s-%s-%s)" % (m.group(1), m.group(2), m.group(3))


def bounds_in(text):
    """-> [ {form, date, pos} ]; a span already claimed by an earlier form is not
    re-reported by a later, looser one."""
    f = despaced(text)
    out, claimed = [], []
    for form, rx in FORMS:
        for m in rx.finditer(f):
            if any(a <= m.start() and m.end() <= b for a, b in claimed):
                continue
            claimed.append((m.start(), m.end()))
            out.append({"form": form, "date": iso(m), "pos": m.start()})
    return sorted(out, key=lambda x: x["pos"])


def channels(period):
    out = []
    p = os.path.join(PDF_DIR, "dwcon_%s.pdf" % period)
    if os.path.exists(p):
        import fitz
        with fitz.open(p) as doc:
            out.append(("text_layer", "\n".join(doc[i].get_text()
                                                for i in range(doc.page_count))))
    q = os.path.join(OCR_DIR, "59_ocr_full_%s.txt" % period)
    if os.path.exists(q):
        out.append(("ocr59", io.open(q, encoding="utf-8").read()))
    return out


def window_of(bs):
    """From classified bounds only. -> (lo, hi, how) or (None, None, why)."""
    lo = next((b["date"] for b in bs if b["form"] == "lower_words"), None)
    hi = next((b["date"] for b in bs if b["form"] in ("upper_words", "upper_op")),
              None)
    if lo and hi:
        return lo, hi, "both bounds classified"
    if lo and not hi:
        return lo, None, "lower bound only; upper bound not read"
    if hi and not lo:
        return None, hi, "upper bound only; lower bound not read"
    return None, None, "no classified bound"


def aligns(date_iso, period):
    return bool(date_iso) and date_iso[:7] == period


def main():
    doc = {"what": "the declared query window per issue, both channels",
           "instrument_version": "v2 -- widened forms; unread bounds reported as "
                                 "unread, unclassifiable bounds kept separate",
           "why": "if the issues do not each cover their own month, the E9 series "
                  "is not a like-for-like monthly series",
           "issues": {}}
    any_found = False

    for per in PERIODS:
        rec = {"channels": {}}
        for name, text in channels(per):
            bs = bounds_in(text)
            if bs:
                any_found = True
            lo, hi, how = window_of(bs)
            days = None
            if lo and hi and "INVALID" not in lo and "INVALID" not in hi:
                try:
                    days = (dt.date.fromisoformat(hi) - dt.date.fromisoformat(lo)).days
                except ValueError:
                    days = None
            rec["channels"][name] = {
                "bounds": bs,
                "lower_bound": lo, "upper_bound": hi, "n_days": days,
                # A THIRD, ARITHMETIC witness. The window is half-open
                # [lower, upper), so its span must equal the length of the month
                # it starts in -- 30 for June, 31 for July/August, 30 for
                # September, 31 for October. A span that matches the LOWER
                # bound's month is what an aligned window looks like; a span that
                # matches while the label does not is what a mislabelled window
                # looks like.
                "span_equals_lower_month_length": (
                    None if (days is None or not lo or "INVALID" in lo)
                    else days == _month_len(lo)),
                "derivation": how,
                "lower_aligns_to_issue_month": aligns(lo, per),
                "upper_aligns_to_next_month": None if not hi else hi[:7] == _next(per),
                "unclassified_bounds": [b for b in bs if b["form"].startswith("UNCLASS")],
            }
        doc["issues"][per] = rec

    if not any_found:
        print("NO BOUND IN ANY DOCUMENT -- the probe and the object disagree about "
              "what a bound looks like; refusing to emit")
        return 2

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2, sort_keys=True)

    print("%-9s %-11s %-12s %-12s %-6s %-9s %-9s %s"
          % ("issue", "channel", "lower", "upper", "days", "lo=own", "hi=next",
             "derivation"))
    for per in PERIODS:
        for name, v in sorted(doc["issues"][per]["channels"].items()):
            if not v["bounds"]:
                continue
            print("%-9s %-11s %-12s %-12s %-6s %-9s %-9s %s"
                  % (per, name, v["lower_bound"] or "-", v["upper_bound"] or "-",
                     v["n_days"] if v["n_days"] is not None else "-",
                     v["lower_aligns_to_issue_month"],
                     v["upper_aligns_to_next_month"], v["derivation"]))
    print()
    print("UNCLASSIFIED bounds (OCR fragments; sign not recoverable, not guessed):")
    for per in PERIODS:
        for name, v in sorted(doc["issues"][per]["channels"].items()):
            for b in v["unclassified_bounds"]:
                print("   %s/%s  %s  %s" % (per, name, b["date"], b["form"]))
    print()
    print("issues with NO bound read in any channel: %s"
          % ", ".join(p for p in PERIODS
                      if not any(v["bounds"] for v in doc["issues"][p]["channels"].values())))
    print("-> %s" % os.path.relpath(OUT, ROOT))
    return 0


def _next(period):
    y, m = int(period[:4]), int(period[5:7])
    return "%04d-%02d" % (y + (m // 12), (m % 12) + 1)


def _month_len(iso_date):
    y, m = int(iso_date[:4]), int(iso_date[5:7])
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return (dt.date(ny, nm, 1) - dt.date(y, m, 1)).days


if __name__ == "__main__":
    sys.exit(main())
