#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""73 -- the query window and its result count, in the SAME screenshot.

72_ found that the legible window on the 2025-10 page starts 2025-09-01, and that
2025-08's screenshot says `为您找到6826条匹配结果` where 6826 is exactly the second
headline figure for 2025-08. If that hold-up holds generally, then the headline
figures are not "the month's totals" -- they are the hit counts of a query whose
window is written on the page, and the window is checkable.

This dumps a wide window around each occurrence of the query-result phrase so the
(window, count) PAIR can be read together, per issue. It reports the pair; it
does not interpret it.

Read-only.
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

HITS = ["为您找到", "匹配结果", "录入时间", "条匹配",
        "release_time", "timestamp", "发布时间大于"]


def flat(s):
    return re.sub(r"\s+", " ", s)


def texts(period):
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
        seen = set()
        for name, text in texts(per):
            f = flat(text)
            for h in HITS:
                for m in re.finditer(re.escape(h), f):
                    a = max(0, m.start() - 170)
                    seg = f[a:m.start() + 170]
                    key = seg[:80]
                    if key in seen:
                        continue
                    seen.add(key)
                    print("  [%s] %s" % (name, seg))
                if h in f:
                    break
        if not seen:
            print("  (none of %s in this issue, any channel)" % "/".join(HITS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
