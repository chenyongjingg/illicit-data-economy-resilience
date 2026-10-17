#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""70 -- is 69_'s silence about country_us / ransom_* a finding, or a broken probe?

69_ reported `-` for country_us, ransom_groups and ransom_events in ALL nine
issues, including the four whose PDFs do have a text layer. A field that is empty
everywhere is the shape a broken regex makes, not the shape an absence makes.
This prints the literal hit counts of the words those regexes depend on, and the
context around them, so the `-` can be classified:

  words absent        -> the field is genuinely absent (or lives in an image)
  words present, rx fails -> 69_'s regex was wrong; 69_'s `-` means nothing

Cheap and read-only. It decides nothing about E9; it decides whether 69_'s
negative is admissible.
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

# The literal words each 69_ regex depends on. If one of these is missing from a
# document, 69_'s `-` for that field is uninformative.
TERMS = ["匿名社交社群情报总数量", "有效情报", "高价值买卖情报",
         "国家分类", "勒索", "黑客组织", "有效数据泄露样例下载",
         "美国", "总数量"]


def flat(s):
    return re.sub(r"\s+", " ", s)


def channels(period):
    """-> list of (channel_name, text) available for this period."""
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
    print("literal term counts per document/channel")
    print("%-9s %-11s %s" % ("issue", "channel", "  ".join("%-12s" % t[:11]
                                                           for t in TERMS)))
    ctx = {}
    for per in PERIODS:
        for name, text in channels(per):
            f = flat(text)
            counts = [f.count(t) for t in TERMS]
            print("%-9s %-11s %s" % (per, name, "  ".join("%-12d" % c for c in counts)))
            for t in ("勒索", "黑客组织", "国家分类"):
                for m in re.finditer(re.escape(t), f):
                    ctx.setdefault((per, name, t), []).append(
                        f[max(0, m.start() - 40):m.start() + 60])

    print()
    print("=== context around the terms 69_ needed (first 2 each)")
    for (per, name, t), hits in ctx.items():
        for h in hits[:2]:
            print("%s %s [%s] ...%s..." % (per, name, t, h))
        print()

    print("=== the anon_total context, to check 69_'s extraction is not an artifact")
    for per in PERIODS:
        for name, text in channels(per):
            f = flat(text)
            for m in re.finditer("匿名社交社群情报总数量", f):
                print("%-9s %-11s ...%s..." % (per, name, f[m.start():m.start() + 90]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
