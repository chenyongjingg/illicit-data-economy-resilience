#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""59_E9_ocr_full.py -- OCR every page of the five issues whose body is not text.

Why: 57_ proved the headline metrics are on p.6 but invisible to text extraction.
That leaves a larger question the paper cannot answer from 57_ alone -- whether
the REST of those reports is equally unreadable, and whether the p.6-only scan
missed any other statement of the series. This closes that by OCRing the whole
document.

This is a RECOVERY, not a re-derivation: it does not touch the series in 57_.
It produces per-issue sidecar text so that any later claim about these five
reports is checkable against text instead of against someone's summary of a
picture.

Bounded and honest:
  * only the five issues that have no usable text layer (01-04 stay on the text
    layer; OCRing them would add nothing and invite drift),
  * every page, no sampling,
  * per-page char counts recorded, so "OCR produced nothing here" is visible
    per page rather than averaged away,
  * a failure on one page is recorded as that page's error, never as an empty
    page.
"""
import glob
import json
import os
import re
import sys
import time

import fitz
from rapidocr_onnxruntime import RapidOCR

PDFDIR = "/root/cis/data/external/dwcon"
OUTDIR = "/root/cis/results"
TXTDIR = os.path.join(OUTDIR, "59_ocr_full_text")
RES = os.path.join(OUTDIR, "59_E9_ocr_full.json")
DPI = 200
SILENT = ["2025-06", "2025-07", "2025-08", "2025-10", "2025-11"]
KEY = "情报"


def main():
    os.makedirs(TXTDIR, exist_ok=True)
    engine = RapidOCR()
    avail = {os.path.basename(p): p for p in glob.glob(os.path.join(PDFDIR, "*.pdf"))}
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "what": "full-document OCR of the five issues with no usable text layer",
           "instrument": "rapidocr_onnxruntime, fitz get_pixmap(dpi=%d)" % DPI,
           "issues": {}}

    for per in SILENT:
        hits = [v for k, v in avail.items() if per in k]
        if not hits:
            out["issues"][per] = {"error": "no pdf"}
            continue
        doc = fitz.open(hits[0])
        t0 = time.time()
        pages, chars_total, key_pages = [], 0, []
        buf = []
        for i in range(doc.page_count):
            png = os.path.join(TXTDIR, "_tmp_%s_%03d.png" % (per, i + 1))
            doc[i].get_pixmap(dpi=DPI).save(png)
            try:
                res, _ = engine(png)
                txt = "\n".join(r[1] for r in (res or []))
                err = None
            except Exception as exc:                            # noqa: BLE001
                txt, err = "", "%s: %s" % (type(exc).__name__, exc)
            finally:
                try:
                    os.remove(png)
                except OSError:
                    pass
            chars_total += len(txt)
            nk = txt.count(KEY)
            if nk:
                key_pages.append(i + 1)
            pages.append({"page": i + 1, "chars": len(txt), "key_count": nk,
                          "error": err})
            buf.append("\n===== page %d =====\n%s" % (i + 1, txt))
            if (i + 1) % 10 == 0:
                print("   %s page %d/%d  chars so far %d"
                      % (per, i + 1, doc.page_count, chars_total), flush=True)
        doc.close()
        txtpath = os.path.join(TXTDIR, "59_ocr_full_%s.txt" % per)
        with open(txtpath, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(buf))
        secs = round(time.time() - t0, 1)
        out["issues"][per] = {
            "pdf": os.path.basename(hits[0]), "n_pages": len(pages),
            "total_chars": chars_total, "seconds": secs,
            "pages_with_keyword": key_pages,
            "n_pages_with_zero_chars": sum(1 for p in pages if p["chars"] == 0),
            "pages": pages, "text": txtpath,
        }
        print("%s  pages=%d  chars=%d  key_pages=%s  zero_char_pages=%d  %.0fs"
              % (per, len(pages), chars_total, key_pages,
                 out["issues"][per]["n_pages_with_zero_chars"], secs), flush=True)

    with open(RES, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("wrote %s" % RES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
