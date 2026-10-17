#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""72 -- dump the raw context around 录入时间, so 71_'s patchy coverage can be
classified instead of guessed at.

71_ recovered one clean window (2025-08) and 1/2 halves elsewhere. That is not
enough to say anything about window lengths, and it is exactly the situation
where the tempting move -- "the windows probably differ" -- is a claim about the
documents made from a broken probe. This prints what is actually there.

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


def flat(s):
    return re.sub(r"\s+", " ", s)


def channels(period):
    out = []
    p = os.path.join(PDF_DIR, "dwcon_%s.pdf" % period)
    if os.path.exists(p):
        import fitz
        with fitz.open(p) as doc:
            for i in range(doc.page_count):
                t = doc[i].get_text()
                if "录入时间" in t or "大于等于" in t:
                    out.append(("text_layer", i + 1, t))
    q = os.path.join(OCR_DIR, "59_ocr_full_%s.txt" % period)
    if os.path.exists(q):
        out.append(("ocr59", "?", io.open(q, encoding="utf-8").read()))
    return out


def main():
    for per in PERIODS:
        print("=" * 78)
        print("ISSUE %s" % per)
        hits = 0
        for name, page, text in channels(per):
            f = flat(text)
            for m in re.finditer("录入时间", f):
                hits += 1
                print("  [%s p%s] ...%s..." % (name, page, f[m.start():m.start() + 110]))
            # the >= / <= signs alone, in case the words were split
            for m in re.finditer(r"[≥≤]|>=|<=", f):
                seg = f[max(0, m.start() - 46):m.start() + 40]
                if "录入" in seg or "时间" in seg:
                    print("  [%s p%s] SIGN ...%s..." % (name, page, seg))
        if not hits:
            print("  (no 录入时间 in this issue, in any channel)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
