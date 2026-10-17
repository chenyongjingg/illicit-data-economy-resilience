#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""77_E9_tab_render.py -- crop the p.6 tab-row band to PNG, for inspection by a
witness that is not the OCR engine.

WHY. `76_` concludes, from x-geometry, that the p.6 tab bar has the same eight
categories in the same order in every issue EXCEPT that the 7th is
`数据泄露情报` in 2025-01..04 and `暗网情报` in 2025-06..11. That conclusion
currently rests on a single OCR engine -- the same one `59_` used, so agreement
between them is agreement between two applications of one instrument, not two
witnesses (the project has been burned by exactly this: Python and bash both
blind to LaTeX comments, both reporting 88; truth 87).

The independent witness has to be a different OBJECT, not a different tool. This
script emits the raw pixels of the band so a human eye can read the labels off
the screenshot directly.

Crops generously: the whole tab bar plus the row beneath it, for every issue,
concatenated vertically into one contact sheet so the months can be compared
without opening nine files.
"""
from __future__ import annotations

import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = sys.argv[1] if len(sys.argv) > 1 else "/root/cis/data/external/dwcon"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/root/cis/results/77_tab_band.png"
PAGE_INDEX = 5
DPI = 200
# The tab band sits near the foot of p.6 in every issue (76_: label row y ~ 742-861
# at 200 dpi, counts ~20-33 px below). Crop wide and tall enough to be sure.
Y0, Y1 = 700, 900
X0, X1 = 200, 1500
SCALE = 0.75          # shrink to keep the contact sheet readable when viewed


def main():
    import fitz

    pdfs = sorted(glob.glob(os.path.join(SRC, "dwcon_*.pdf")))
    if not pdfs:
        print("no dwcon_*.pdf under %s" % SRC)
        return 3

    tiles = []
    for p in pdfs:
        key = re.search(r"(dwcon_\d{4}-\d{2})", os.path.basename(p)).group(1)
        doc = fitz.open(p)
        page = doc[PAGE_INDEX]
        # clip is in PDF points (72/inch); the 76_ coords are at DPI px
        f = 72.0 / DPI
        clip = fitz.Rect(X0 * f, Y0 * f, X1 * f, Y1 * f)
        pix = page.get_pixmap(dpi=int(DPI * SCALE), clip=clip)
        fn = "/tmp/%s_band.png" % key
        pix.save(fn)
        tiles.append((key, fn, pix.width, pix.height))
        print("%s  band %dx%d" % (key, pix.width, pix.height))

    # stack into one sheet and label each strip with its month
    import fitz as fz
    W = max(t[2] for t in tiles)
    H = sum(t[3] for t in tiles) + 18 * len(tiles)
    sheet = fz.open()
    pg = sheet.new_page(width=W, height=H)
    y = 0
    for key, fn, w, h in tiles:
        pg.insert_text(fz.Point(4, y + 12), key, fontsize=11)
        y += 18
        pg.insert_image(fz.Rect(0, y, w, y + h), filename=fn)
        y += h
    sheet.save(OUT)
    print("wrote %s (%dx%d)" % (OUT, W, H))
    return 0


if __name__ == "__main__":
    sys.exit(main())
