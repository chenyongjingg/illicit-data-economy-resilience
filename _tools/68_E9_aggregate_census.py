#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""68 -- census of stated aggregates in the five full-document OCR texts.

WHY THIS EXISTS
---------------
C-113 registers a caveat that limits how E9's anchor may be read: the reports
state SEVERAL section-level aggregates, so taking section 一's pair is itself a
selection that has to be disclosed. Until now that caveat was an assertion about
the documents, because only p.6 had been OCR'd. `59_E9_ocr_full.py` has since
OCR'd all pages of the five text-layer-less issues (C-122), so the assertion is
now checkable and this converts it into a count with its denominators.

WHAT IT DOES NOT DO
-------------------
It does not decide which aggregate E9 should use, and it does not claim the
census is complete: it reads OCR text, so a garbled number is a miss. The count
is therefore a LOWER bound on the aggregates present, and that is stated in the
output rather than left implicit.

POSITIVE CONTROL
----------------
The detector must find the known p.6 headline pair (有效情报 / 高价值买卖情报)
on page 6 of every issue. If it cannot find something already known to be there,
it cannot be trusted to report that other things are absent -- so the control
runs first and the tool refuses to emit if it fails.
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
SRC = os.path.join(RES, "59_ocr_full_text")
OUT = os.path.join(RES, "68_E9_aggregate_census.json")

PERIODS = ["2025-06", "2025-07", "2025-08", "2025-10", "2025-11"]

# An aggregate = a number immediately followed by a counting unit.
UNIT = r"(?:份|条|起|次|个|人次)"
AGG = re.compile(r"(\d[\d,，]{1,})\s*(" + UNIT + r")")
PAGE = re.compile(r"=====\s*page\s+(\d+)\s*=====")
# Words that mark a statement as a total rather than an incidental count.
TOTAL_WORDS = ("共", "合计", "总计", "累计", "其中", "总量", "共计")


def pages_of(text):
    """-> [(page_no, page_text)]"""
    marks = [(m.start(), int(m.group(1)), m.end()) for m in PAGE.finditer(text)]
    out = []
    for i, (_s, n, e) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out.append((n, text[e:end]))
    return out


def census_page(text):
    """-> [ {value, unit, context} ] for one page."""
    out = []
    for m in AGG.finditer(text):
        ctx = re.sub(r"\s+", " ", text[max(0, m.start() - 34):m.end() + 22]).strip()
        out.append({"value": m.group(1), "unit": m.group(2), "context": ctx,
                    "is_total_wording": any(w in ctx for w in TOTAL_WORDS)})
    return out


def is_headline_pair(match_text):
    """The p.6 pair is introduced by these two phrases."""
    return ("有效情报" in match_text) or ("高价值买卖情报" in match_text)


def main():
    if not os.path.isdir(SRC):
        print("missing %s -- run 59_ first" % os.path.relpath(SRC, ROOT))
        return 2

    doc = {"what": "census of stated aggregates across every page of the five "
                   "full-document OCR texts",
           "instrument": "regex over results/59_ocr_full_text/*.txt",
           "unit_pattern": UNIT,
           "lower_bound_note":
               "Counts are a LOWER BOUND: the source is OCR text, so a garbled "
               "number is a miss. This tool reports what it found, not what exists.",
           "issues": {}}
    control_failures = []

    for per in PERIODS:
        p = os.path.join(SRC, "59_ocr_full_%s.txt" % per)
        if not os.path.exists(p):
            print("MISSING %s" % p)
            return 2
        text = io.open(p, encoding="utf-8").read()
        pgs = pages_of(text)

        per_page = []
        headline = []
        total = 0
        for n, t in pgs:
            hits = census_page(t)
            if not hits:
                continue
            total += len(hits)
            for h in hits:
                if is_headline_pair(h["context"]):
                    headline.append({"page": n, "value": h["value"],
                                     "unit": h["unit"], "context": h["context"]})
            per_page.append({"page": n, "n": len(hits),
                             "with_total_wording": sum(1 for h in hits
                                                       if h["is_total_wording"]),
                             "hits": hits})

        # POSITIVE CONTROL: the p.6 pair must be found, on page 6, twice.
        p6 = [h for h in headline if h["page"] == 6]
        if len(p6) < 2:
            control_failures.append("%s: found %d/2 headline figures on page 6"
                                    % (per, len(p6)))

        doc["issues"][per] = {
            "n_pages": len(pgs),
            "n_aggregates": total,
            "pages_with_aggregates": len(per_page),
            "n_pages_without_any": len(pgs) - len(per_page),
            "headline_figures": headline,
            "n_headline_figures": len(headline),
            "per_page": per_page,
            "text": os.path.relpath(p, ROOT).replace(os.sep, "/"),
        }

    if control_failures:
        print("POSITIVE CONTROL FAILED -- refusing to emit:")
        for c in control_failures:
            print("   %s" % c)
        return 2

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2, sort_keys=True)

    print("positive control: page-6 headline pair found in all %d issues  OK"
          % len(PERIODS))
    print()
    print("%-9s %-7s %-12s %-14s %s" % ("issue", "pages", "aggregates",
                                        "pages w/ agg", "h/figs (page)"))
    for per in PERIODS:
        r = doc["issues"][per]
        hp = sorted({h["page"] for h in r["headline_figures"]})
        print("%-9s %-7d %-12d %-14d %d %s"
              % (per, r["n_pages"], r["n_aggregates"],
                 r["pages_with_aggregates"], r["n_headline_figures"], hp))
    print()
    print("-> %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
