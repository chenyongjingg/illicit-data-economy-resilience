#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""56_E9_render_pages.py -- rasterise the pages in question so they can be LOOKED AT.

The dispute is whether the five "silent" issues state the headline metrics in an
image, where no text extractor can see them. Every instrument in play (fitz,
pypdf, my witness, the peer's five fitz call variants) shares one blind spot:
none of them can see a picture of a number. Agreement between instruments that
share a blind spot carries no information about what is behind it.

So: stop extracting and render. p.6 is where 01-04 carry the metrics as text.
Render p.6 of a readable issue (positive control) and p.6 of a silent one, plus
neighbouring pages, and look.
"""
import os
import sys

import fitz

PDFDIR = r"D:\CIS\data\external\dwcon"
OUTDIR = r"D:\CIS\results\_e9_pages"

TARGETS = [
    ("2025-01", [4, 5, 6, 7]),        # positive control: p.6 has the text block
    ("2025-07", [4, 5, 6, 7]),        # silent
]


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    import glob
    avail = {os.path.basename(p): p for p in glob.glob(os.path.join(PDFDIR, "*.pdf"))}
    for period, pages in TARGETS:
        hit = [v for k, v in avail.items() if period in k]
        if not hit:
            print("no pdf for %s" % period)
            continue
        doc = fitz.open(hit[0])
        for pno in pages:
            if pno > doc.page_count:
                continue
            pg = doc[pno - 1]
            pix = pg.get_pixmap(dpi=140)
            out = os.path.join(OUTDIR, "%s_p%02d.png" % (period, pno))
            pix.save(out)
            print("%s  page %d  %dx%d  %d bytes"
                  % (out, pno, pix.width, pix.height, os.path.getsize(out)))
        doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
