#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""65 -- Read the publisher's own screenshot on p.6 for EVERY issue, same engine.

WHY THIS EXISTS
---------------
A peer read the p.6 screenshots and reported that the boxed value tracks the
issue's MONTH BAND (01-02 box bullet 1, 03-11 box bullet 2) rather than the
highlighted TAB LABEL.  Its decisive row is 2025-04: label `数据泄露情报` (which
their own split finds only in 01-04) paired with a boxed value they read as
3,999 -- a bullet-2 value.

If true this matters for the paper, because bullet 1's acceleration begins in
March, the same month the band changes.  A method change and a level change at
the same boundary cannot be separated from the PDFs.

But the peer read 2025-04 from a crop, and could not read 2025-03 at all ("value
row fell below the crop").  This script reads p.6 of EVERY issue with one
engine, one dpi, no cropping, so the rows are comparable to each other.

It does NOT re-derive the bullets -- those come from 51_/57_.  It reads only
what the publisher's own screenshot shows, and prints, for each issue:
  * every 3-7 digit number OCR finds on p.6, in reading order
  * which of those equal bullet 1 or bullet 2 for that issue
  * which category labels appear
  * the query-window text if legible

CONTROL
-------
2025-06 is included: its box is known from 57_ to read 5,232 (bullet 2).  If
this script does not reproduce that, its readings for the other months carry no
weight.
"""
import glob
import io
import json
import os
import re
import sys

import fitz
from rapidocr_onnxruntime import RapidOCR

PDFDIR = "/root/cis/data/external/dwcon"
OUTDIR = "/root/cis/results"
DPI = 200
PAGE = 6                      # 1-based; the data page under the templated layout

PERIODS = ["2025-01", "2025-02", "2025-03", "2025-04",
           "2025-06", "2025-07", "2025-08", "2025-10", "2025-11"]

# From 51_/57_: the two stated series.  Used ONLY to label what OCR finds,
# never to correct it.
BULLETS = {
    "2025-01": (96082, 4749), "2025-02": (140800, 4955),
    "2025-03": (356323, 5880), "2025-04": (509880, 3999),
    "2025-06": (1140767, 5232), "2025-07": (1140767, 5822),
    "2025-08": (68904, 6826), "2025-10": (336661, 6176),
    "2025-11": (436427, 6889),
}
LABELS = ["数据泄露情报", "暗网情报", "泄露情报", "深网", "电信诈骗"]

NUM = re.compile(r"[0-9][0-9,，]{2,}")
FW = {ord(c): ord("0") + i for i, c in enumerate("０１２３４５６７８９")}


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    avail = {os.path.basename(p): p for p in glob.glob(os.path.join(PDFDIR, "*.pdf"))}
    engine = RapidOCR()
    out = {"instrument": "rapidocr_onnxruntime over fitz render, dpi=%d, page=%d"
                         % (DPI, PAGE),
           "question": "what does the publisher's own p.6 screenshot show?",
           "issues": {}}

    for per in PERIODS:
        hits = [v for k, v in avail.items() if per in k]
        if not hits:
            out["issues"][per] = {"error": "no pdf"}
            print("%s  NO PDF" % per, flush=True)
            continue
        doc = fitz.open(hits[0])
        if doc.page_count < PAGE:
            out["issues"][per] = {"error": "needs %d pages, has %d"
                                           % (PAGE, doc.page_count)}
            print("%s  TOO SHORT" % per, flush=True)
            doc.close()
            continue
        png = os.path.join(OUTDIR, "_tmp65_%s.png" % per)
        doc[PAGE - 1].get_pixmap(dpi=DPI).save(png)
        doc.close()
        try:
            res, _ = engine(png)
        except Exception as exc:                              # noqa: BLE001
            out["issues"][per] = {"error": "%s: %s" % (type(exc).__name__, exc)}
            print("%s  OCR ERROR %s" % (per, exc), flush=True)
            continue
        finally:
            try:
                os.remove(png)
            except OSError:
                pass

        lines = [r[1] for r in (res or [])]
        body = "\n".join(lines).translate(FW)
        nums = []
        for m in NUM.finditer(body):
            try:
                nums.append(int(re.sub(r"[,，\s]", "", m.group(0))))
            except ValueError:
                pass
        b1, b2 = BULLETS.get(per, (None, None))
        tags = []
        for v in nums:
            t = ""
            if v == b1:
                t = "=bullet1"
            elif v == b2:
                t = "=bullet2"
            tags.append({"value": v, "tag": t})
        out["issues"][per] = {
            "pdf": os.path.basename(hits[0]),
            "dpi": DPI,
            "labels_found": [L for L in LABELS if L in body],
            "numbers": tags,
            "n_ocr_lines": len(lines),
            "raw_lines": lines,
            "bullet1": b1, "bullet2": b2,
            "values_equal_to_bullet1": [v for v in nums if v == b1],
            "values_equal_to_bullet2": [v for v in nums if v == b2],
            "values_matching_neither": [v for v in nums if v not in (b1, b2)],
        }
        print("%s  labels=%s  bullet1=%s bullet2=%s"
              % (per, out["issues"][per]["labels_found"], b1, b2), flush=True)
        print("      nums=%s" % nums, flush=True)
        print("      =b1 %s   =b2 %s   neither %s"
              % (out["issues"][per]["values_equal_to_bullet1"],
                 out["issues"][per]["values_equal_to_bullet2"],
                 out["issues"][per]["values_matching_neither"]), flush=True)

    # Positive control on the one issue whose box 57_ already recorded.
    c = out["issues"].get("2025-06") or {}
    ctrl = 5232 in (c.get("numbers") and [n["value"] for n in c["numbers"]] or [])
    out["positive_control"] = {
        "issue": "2025-06", "requirement": "OCR finds 5232 on p.6",
        "passes": bool(ctrl),
        "why": "57_ independently recorded 2025-06's boxed value as 5232; if this "
               "engine cannot find it, its readings for other months are empty.",
    }
    with io.open(os.path.join(OUTDIR, "65_E9_shot_band.json"), "w",
                 encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print("\npositive_control passes=%s" % ctrl)
    return 0


if __name__ == "__main__":
    sys.exit(main())
