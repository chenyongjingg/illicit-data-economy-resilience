#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""57_E9_ocr_p6.py -- recover the E9 headline series from page 6 by OCR.

WHY THIS EXISTS
    Every text extractor in play (fitz, pypdf, my witness, five fitz call
    variants) returns nothing for the CJK body of 2025-06/07/08/10/11. That is a
    fact about a text layer, NOT about the reports: rendering p.6 of 2025-07 and
    looking at it shows 深网和暗网有效情报 1,140,767 份 plainly on the page. A
    matcher that reads text cannot see a document whose glyphs are not text.

    So the curve's "4 periods" is an artefact of the extraction route, not a
    property of the source. This script opens the second route.

THE INSTRUMENT IS VALIDATED BEFORE IT IS USED
    For 2025-01..04 the same two sentences ARE in the text layer, so their
    values are known independently (51_E9_series.json). OCR runs on those four
    too. If OCR does not reproduce all four known pairs, its readings for the
    other five are not evidence and the script says so. A measurement instrument
    that has not been checked against a known input is not an instrument.

    The two routes have different blind spots (one needs glyph->Unicode
    mappings, the other needs pixels), so agreement between them is informative
    -- unlike the earlier case where two extractors shared one blind spot.

NOTHING IS INTERPOLATED. A month OCR cannot read stays None.
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
RES = os.path.join(OUTDIR, "57_E9_ocr_p6.json")
PAGE = 6                      # 1-indexed; the data page, same position in all 9
DPI = 250

# NOTE the full-width comma in the class. OCR returns Chinese punctuation:
# 2025-03 reads '5，880份' with U+FF0C, which an ASCII-only class cannot match.
# The v1 pattern therefore reported hv=None for 03/04 while the captured line
# plainly contained 5,880 and 3,999. The four known issues are the control that
# caught this; uncaught, it would have turned a full-width comma in the five
# image-only issues into a "the report states no such number" finding.
PAT_EFF = re.compile(r"有效情报\s*([\d,，]+)\s*份")
PAT_HV = re.compile(r"高价值买卖情报\s*([\d,，]+)\s*份")

# Independent truth for the four issues whose text layer carries the sentences.
KNOWN = {"2025-01": (96082, 4749), "2025-02": (140800, 4955),
         "2025-03": (356323, 5880), "2025-04": (509880, 3999)}


def despaced(t):
    t = re.sub(r"(?<=\d)\s+(?=[\d,，])", "", t)
    t = re.sub(r"(?<=[,，])\s+(?=\d)", "", t)
    return t


def val(pat, txt):
    m = pat.search(despaced(txt))
    if not m:
        return None
    return int(re.sub(r"[,，\s]", "", m.group(1)))


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    engine = RapidOCR()
    pdfs = sorted(glob.glob(os.path.join(PDFDIR, "*.pdf")))
    per, series_eff, series_hv, controls = {}, {}, {}, {}

    for p in pdfs:
        base = os.path.basename(p)
        period = (re.search(r"(\d{4}-\d{2})", base) or [None, None])[1]
        doc = fitz.open(p)
        if PAGE > doc.page_count:
            doc.close()
            continue
        png = os.path.join(OUTDIR, "57_ocr_%s_p%02d.png" % (period, PAGE))
        doc[PAGE - 1].get_pixmap(dpi=DPI).save(png)
        doc.close()

        t0 = time.time()
        res, _ = engine(png)
        texts = [r[1] for r in (res or [])]
        txt = "\n".join(texts)
        eff, hv = val(PAT_EFF, txt), val(PAT_HV, txt)
        secs = round(time.time() - t0, 1)

        side = os.path.join(OUTDIR, "57_ocr_%s_p%02d.txt" % (period, PAGE))
        with open(side, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)

        line_eff = next((s for s in texts if "有效情报" in s), None)
        line_hv = next((s for s in texts if "高价值买卖情报" in s), None)
        per[base] = {"period": period, "ocr_lines": len(texts),
                     "ocr_chars": len(txt), "seconds": secs,
                     "effective_items": eff, "high_value_items": hv,
                     "line_effective": line_eff, "line_high_value": line_hv,
                     "sidecar": side}
        if eff is not None:
            series_eff[period or base] = eff
        if hv is not None:
            series_hv[period or base] = hv

        if period in KNOWN:
            ke, kh = KNOWN[period]
            ok = (eff == ke and hv == kh)
            controls[period] = {"text_layer": [ke, kh], "ocr": [eff, hv],
                                "agree": ok}
            print("%s  OCR eff=%-10s hv=%-7s | text_layer %s/%s  %s"
                  % (period, eff, hv, ke, kh, "AGREE" if ok else "*** DISAGREE ***"))
        else:
            print("%s  OCR eff=%-10s hv=%-7s | (no text layer; OCR is the only route)"
                  % (period, eff, hv))
        print("      eff line: %r" % (line_eff or "")[:100])
        print("      hv  line: %r" % (line_hv or "")[:100])

    n_ctrl = len(controls)
    n_agree = sum(1 for v in controls.values() if v["agree"])
    validated = (n_ctrl == 4 and n_agree == 4)

    payload = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "what": "E9 headline series, p.%d, via RapidOCR on rendered pages" % PAGE,
        "instrument": "rapidocr_onnxruntime on fitz get_pixmap(dpi=%d)" % DPI,
        "validation": {
            "controls": controls,
            "n_controls": n_ctrl, "n_agree": n_agree,
            "validated": validated,
            "meaning": ("OCR reproduces every known value, so its readings on the "
                        "issues with no text layer are evidence"
                        if validated else
                        "OCR did NOT reproduce the known values; its readings on "
                        "the other issues are NOT evidence"),
        },
        "n_periods": len(set(list(series_eff) + list(series_hv))),
        "series": {"effective_items": series_eff, "high_value_items": series_hv},
        "per_report": per,
    }
    with open(RES, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print("\n=== validation: %d/%d controls agree -> validated=%s"
          % (n_agree, n_ctrl, validated))
    print("=== SERIES (%d periods) ==="
          % len(set(list(series_eff) + list(series_hv))))
    for k in sorted(set(list(series_eff) + list(series_hv))):
        print("   %-10s eff=%-10s hv=%s"
              % (k, series_eff.get(k, "-"), series_hv.get(k, "-")))
    print("wrote %s" % RES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
