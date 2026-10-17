#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""69 -- the OTHER monthly aggregates in the same reports.

WHY THIS EXISTS
---------------
C-113 warned that the reports state several section-level aggregates, so reading
E9 off section 一's pair is a selection. Until the full documents were available
that warning was an assertion; the census (68_) turned it into a count. This goes
one step further and extracts a SECOND per-issue series that the same documents
state, so the two can be compared directly.

The finding this exists to test: the two series do not move together. On the five
issues with full OCR, the p.6 anchor collapses at 2025-08 and then recovers,
while the anonymous-social-community total does the opposite -- it stays high
through 2025-10 and collapses at 2025-11. If that holds across all nine issues,
then "the" E9 curve is a property of a chosen aggregate, not of the phenomenon,
and that is a fact the paper has to state rather than a caveat it can note.

TWO CHANNELS, NEVER MERGED
--------------------------
Per issue and per field this reports which instrument supplied the value:
  text_layer  the PDF's own text objects (fitz)
  ocr59       the full-document OCR text in results/59_ocr_full_text/
Values from the two are recorded side by side and compared; a disagreement is
reported as a disagreement, not resolved silently.

POSITIVE CONTROL
----------------
The p.6 headline pair must be found on page 6 of every issue by at least one
channel. If the extractor cannot find something known to be present, its silence
about everything else means nothing, so it refuses to emit when the control fails.
"""
from __future__ import annotations

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
OUT = os.path.join(RES, "69_E9_second_series.json")

PERIODS = ["2025-01", "2025-02", "2025-03", "2025-04",
           "2025-06", "2025-07", "2025-08", "2025-10", "2025-11"]

INSTRUMENT_VERSION = ("v2 -- prints the version into the artefact (v1 is kept at "
                      "69_E9_second_series.prev.json)")

NUM = r"(\d[\d,，]*)"
# Each field: (name, regex, what it counts)
#
# v1 OF THIS LIST WAS WRONG IN A WAY WORTH KEEPING ON THE RECORD. It matched on
# text whose runs of whitespace had been collapsed to single spaces, then
# required each CJK literal to be contiguous. But CJK typesetting breaks a line
# INSIDE a word, and the PDF text layer keeps that as a space -- 2025-11's body
# says "有效数据泄 露样例下载5,760份". So `有效数据泄露样例下载` never matched and
# the field read `-` for every issue. The `-` was the shape of a broken regex,
# not the shape of an absence, and v1 emitted it without a control that could
# have caught this. v2 strips ALL whitespace before matching, so a literal is
# matched whatever the compositor did to it.
FIELDS = [
    ("dwm_effective",   r"有效情报" + NUM + r"份",
     "the p.6 anchor's first figure (DWM, 'deep and dark web effective intel')"),
    ("dwm_high_value",  r"高价值买卖情报" + NUM + r"份",
     "the p.6 anchor's second figure"),
    ("anon_total",      r"匿名社交社群情报总数量" + NUM + r"条",
     "anonymous-social-community intel total"),
    ("anon_samples",    r"有效数据泄露样例下载" + NUM + r"份",
     "sample records downloadable from that channel"),
    ("country_us",      r"共泄露数据" + NUM + r"份",
     "section 一's country breakdown, US, PROSE form ('共泄露数据892份')"),
    ("ransom_groups",   r"活跃的商业黑客组织[^共]{0,20}共" + NUM + r"个",
     "active commercial ransomware groups that month"),
    ("ransom_events",   r"公开的勒索事件共" + NUM + r"件",
     "published ransomware events that month"),
]

# The country row has a SECOND form, used by the four text-layer issues, where
# the figure sits in a table as "美国, 838, 18%". That is not a variant spelling
# of the prose form; it is the same quantity stated by a different element, and
# v1 reported it as absent. Reported separately, never merged into country_us.
US_TABLE = re.compile(r"美国[,，]" + NUM + r"[,，](\d+)%")


def flat(s):
    return re.sub(r"\s+", " ", s)


def despaced(s):
    """For matching CJK literals only: the compositor's line-break spaces inside
    a word are not part of the word (see the v1 note on FIELDS)."""
    return re.sub(r"\s+", "", s)


def from_text(text):
    """-> {field: value} for one document's text (any channel)."""
    f = despaced(text)
    out = {}
    for name, rx, _what in FIELDS:
        m = re.search(rx, f)
        out[name] = m.group(1) if m else None
    us = [{"count": m.group(1), "pct": m.group(2)} for m in US_TABLE.finditer(f)]
    out["country_us_table_rows"] = us
    out["country_us_table"] = us[0]["count"] if us else None
    out["country_us_table_n_matches"] = len(us)
    return out


def _elsewhere(text, rec):
    """Does the issue's own second headline figure appear a SECOND time in the
    same document? It does in the issues whose p.6 carries a query screenshot --
    2025-08 reads `为您找到6826条匹配结果` under a headline value of 6,826.

    Search rule, and the bug that produced it: the headline writes `6,826` and
    the screenshot writes `6826`, so the comparison must be on DIGITS. The first
    version of this function removed the commas AND all whitespace, which
    destroyed token boundaries between numbers -- the tab row `0 5232 0` became
    `052320` and the bounded search for 5232 then found nothing, because it was
    surrounded by digits. Spaces must be kept, commas must not.
    """
    for ch in ("ocr59", "text_layer"):
        v = (rec.get(ch) or {}).get("dwm_high_value")
        if not v:
            continue
        bare = v.replace(",", "").replace("，", "")
        f = re.sub(r"[,，]", "", flat(text))          # keep spaces, drop commas
        n = len(re.findall(r"(?<!\d)" + re.escape(bare) + r"(?!\d)", f))
        return {"value": v, "n_occurrences_in_document": n,
                "appears_more_than_once": n >= 2}
    return None


def pdf_pages(period):
    """-> [(page_no, text)] from the PDF's own text objects, or None."""
    p = os.path.join(PDF_DIR, "dwcon_%s.pdf" % period)
    if not os.path.exists(p):
        return None
    import fitz
    with fitz.open(p) as doc:
        return [(i + 1, doc[i].get_text()) for i in range(doc.page_count)]


def ocr_text(period):
    p = os.path.join(OCR_DIR, "59_ocr_full_%s.txt" % period)
    if not os.path.exists(p):
        return None
    return io.open(p, encoding="utf-8").read()


def main():
    doc = {"what": "the second per-issue aggregate series in the E9 source "
                   "reports, and the p.6 anchor, extracted from two channels",
           "instrument_version": INSTRUMENT_VERSION,
           "fields": {n: w for n, _r, w in FIELDS},
           "channels": {
               "text_layer": "the PDF's own text objects (fitz get_text)",
               "ocr59": "results/59_ocr_full_text/ (only 06/07/08/10/11 exist)"},
           "issues": {}}
    control_failures = []

    for per in PERIODS:
        rec = {"text_layer": None, "ocr59": None, "n_pages_text_layer": None,
               "text_layer_has_any_text": None}

        pgs = pdf_pages(per)
        if pgs is not None:
            joined = "\n".join(t for _n, t in pgs)
            rec["n_pages_text_layer"] = len(pgs)
            rec["text_layer_has_any_text"] = bool(flat(joined).strip())
            rec["text_layer"] = from_text(joined)
            rec["text_layer_p6_pair"] = [
                v for v in (rec["text_layer"].get("dwm_effective"),
                            rec["text_layer"].get("dwm_high_value")) if v]
            rec["text_layer_high_value_elsewhere"] = _elsewhere(joined, rec)

        ot = ocr_text(per)
        if ot is not None:
            rec["ocr59"] = from_text(ot)
            rec["ocr59_p6_pair"] = [
                v for v in (rec["ocr59"].get("dwm_effective"),
                            rec["ocr59"].get("dwm_high_value")) if v]
            rec["ocr59_high_value_elsewhere"] = _elsewhere(ot, rec)

        # CONTROL A: the p.6 pair must appear in at least one channel.
        n_ctl = max(len(rec.get("text_layer_p6_pair") or []),
                    len(rec.get("ocr59_p6_pair") or []))
        if n_ctl < 2:
            control_failures.append("%s: p.6 pair found %d/2 in any channel"
                                    % (per, n_ctl))
        rec["p6_pair_found"] = n_ctl

        # CONTROL B -- the v1 failure class, as a gate. If the literal is in the
        # document and the field still came out empty, the regex is wrong and
        # every `-` this run emits is uninformative, so it must not be delivered.
        for ch, text in (("text_layer", None if pgs is None else joined),
                         ("ocr59", ot)):
            if text is None:
                continue
            if "有效数据泄露样例下载" in despaced(text):
                if not (rec.get(ch) or {}).get("anon_samples"):
                    control_failures.append(
                        "%s/%s: literal 有效数据泄露样例下载 present but anon_samples "
                        "is empty -- regex defect (the v1 class)" % (per, ch))

        doc["issues"][per] = rec

    if control_failures:
        print("POSITIVE CONTROL FAILED -- refusing to emit:")
        for c in control_failures:
            print("   %s" % c)
        return 2

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2, sort_keys=True)

    def cell(rec, ch, field):
        d = rec.get(ch) or {}
        return d.get(field) or "-"

    print("positive control: p.6 pair found for all %d issues  OK" % len(PERIODS))
    print()
    print("=== the p.6 anchor and the anonymous-social-community series, per issue")
    print("%-9s %-13s %-13s | %-13s %-13s | %s"
          % ("issue", "eff(tl)", "eff(ocr59)", "anon(tl)", "anon(ocr59)", "agree?"))
    for per in PERIODS:
        r = doc["issues"][per]
        a, b = cell(r, "text_layer", "dwm_effective"), cell(r, "ocr59", "dwm_effective")
        c, d = cell(r, "text_layer", "anon_total"), cell(r, "ocr59", "anon_total")
        agree = "n/a"
        if a != "-" and b != "-":
            agree = "yes" if a.replace("，", ",") == b.replace("，", ",") else "NO"
        print("%-9s %-13s %-13s | %-13s %-13s | %s" % (per, a, b, c, d, agree))
    print()
    for ch in ("text_layer", "ocr59"):
        print("=== every field, %s channel" % ch)
        print("%-9s %s" % ("issue", " ".join("%-11s" % n for n, _r, _w in FIELDS)))
        for per in PERIODS:
            r = doc["issues"][per]
            print("%-9s %s" % (per, " ".join("%-11s" % cell(r, ch, n)
                                             for n, _r, _w in FIELDS)))
        print()
    print("=== the US row, both element forms (never merged)")
    print("%-9s %-12s %-12s %s" % ("issue", "prose(共泄露数据)", "table(美国,N,%)",
                                   "table rows"))
    for per in PERIODS:
        r = doc["issues"][per]
        rows = []
        for ch in ("text_layer", "ocr59"):
            rows += (r.get(ch) or {}).get("country_us_table_rows") or []
        print("%-9s %-12s %-12s %s"
              % (per, cell(r, "text_layer", "country_us") if
                 cell(r, "text_layer", "country_us") != "-" else
                 cell(r, "ocr59", "country_us"),
                 (rows[0]["count"] if rows else "-"),
                 "; ".join("%s (%s%%)" % (x["count"], x["pct"]) for x in rows[:4])))
    print()
    print("=== does the second headline figure occur a second time in the doc?")
    for per in PERIODS:
        r = doc["issues"][per]
        e = r.get("ocr59_high_value_elsewhere") or r.get("text_layer_high_value_elsewhere")
        print("%-9s %s" % (per, e))
    print()
    print("-> %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
