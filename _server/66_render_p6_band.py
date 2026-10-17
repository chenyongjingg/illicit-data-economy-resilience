#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""66 -- Render one issue's p.6 at 400 dpi and crop one horizontal band.

WHY
---
Two readers disagree about what the publisher's own screenshot shows on
2025-04's p.6: OCR of a 200-dpi render reads the non-zero tab count as 6,663,
while a peer reading a 170-dpi crop reports 3,999.  3,999 is *also* the value of
the page's second headline bullet, which sits a few lines above the tab row --
so a crop that straddles the two regions would produce exactly the peer's read.

This does not settle it by argument.  It puts the pixels in front of a human-
readable render so the value can be read directly, with no OCR and no regex
between the document and the reader.

Usage: 66_render_p6_band.py <YYYY-MM> <y0> <y1> [dpi]
        y0/y1 are fractions of page height, top-down.
"""
import glob
import os
import sys

import fitz

PDFDIR = "/root/cis/data/external/dwcon"
OUTDIR = "/root/cis/results"


def main():
    per = sys.argv[1]
    y0 = float(sys.argv[2]) if len(sys.argv) > 2 else 0.35
    y1 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.85
    dpi = int(sys.argv[4]) if len(sys.argv) > 4 else 400

    avail = {os.path.basename(p): p for p in glob.glob(os.path.join(PDFDIR, "*.pdf"))}
    hits = [v for k, v in avail.items() if per in k]
    if not hits:
        print("no pdf for %s" % per)
        return 1
    doc = fitz.open(hits[0])
    page = doc[5]                                   # p.6, 0-based index 5
    r = page.rect
    clip = fitz.Rect(r.x0, r.y0 + (r.y1 - r.y0) * y0,
                     r.x1, r.y0 + (r.y1 - r.y0) * y1)
    out = os.path.join(OUTDIR, "66_p6_%s_%.2f_%.2f.png" % (per, y0, y1))
    page.get_pixmap(dpi=dpi, clip=clip).save(out)
    doc.close()
    print("wrote %s  (page %.0fx%.0f pt, clip y %.2f-%.2f, dpi %d)"
          % (out, r.width, r.height, y0, y1, dpi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
