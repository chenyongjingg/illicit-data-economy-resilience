#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""74 -- read the context of every field 69_ v2 newly recovered, before any of
them is published as a series.

69_ v1 could not fire on anon_samples / country_us / ransom_groups /
ransom_events. v2 recovers them for the five OCR'd issues. A regex that fires
for the first time has not been shown to have captured the quantity it names --
it has been shown to have captured something. So this prints the surrounding
text for each, plus the 01-04 case where the prose form of the US row is still
absent and the reason matters (sentence split across a page break vs. no
sentence at all).

Read-only. Decides nothing.
"""
from __future__ import annotations

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "results")
OCR_DIR = os.path.join(RES, "59_ocr_full_text")
PDF_DIR = os.path.join(ROOT, "data", "external", "dwcon")

PERIODS = ["2025-01", "2025-02", "2025-03", "2025-04",
           "2025-06", "2025-07", "2025-08", "2025-10", "2025-11"]

LITERALS = ["有效数据泄露样例下载", "共泄露数据", "活跃的商业黑客组织",
            "公开的勒索事件共"]


def flat(s):
    return re.sub(r"\s+", " ", s)


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


def main():
    for per in PERIODS:
        print("=" * 78)
        print("ISSUE %s" % per)
        for name, text in channels(per):
            f = flat(text)
            g = re.sub(r"\s+", "", f)          # the matching view 69_ v2 uses
            for lit in LITERALS:
                if lit not in g:
                    continue
                i = g.index(lit)
                print("  [%s] %s" % (name, g[max(0, i - 60):i + 90]))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
