#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""55_e9_textlayer_diagnostic.py -- LOCAL diagnostic on the 9 DWC PDFs.

Two live disputes, both about the SAME bytes (all 9 sha256 match between the
two sessions), so both are decidable here without the pod:

  (A) `fitz_chars` in results/51_E9_series.json is 1.8-2.5x the peer's fitz
      reading on 2025-01..04, and equal to within 1 char on the other five.
      A field that is exact for five inputs and 2x for four is not a property
      of the documents. Either my call differs or my version differs -- and if
      I cannot recover which call produced it, the field must be RELABELLED or
      DROPPED, because a number I cannot reproduce is not a measurement.

  (B) The peer says the body is images in ALL nine, that the text layer is
      essentially a TOC on one page, and that 01-04 differ only in whether the
      TOC's Chinese labels rendered. If true, the values I extracted from 01-04
      came from a page I have never looked at, and `present=False` on the other
      five cannot distinguish "not stated" from "in an image".

  Measured, not argued:
    * per-page char counts for all pages of all nine (WHERE is the text?)
    * which page holds the headline scalars (PAT_EFFECTIVE / PAT_HIGHVALUE)
    * which page holds the keyword 情报
    * image count and coverage per page
    * five fitz call variants + pypdf, so (A) gets an answer or an honest blank

Nothing here changes a result file. It is a read-only probe on local copies.
"""
import glob
import json
import os
import re
import sys

PDFDIR = r"D:\CIS\data\external\dwcon"
OUT = r"D:\CIS\results\55_e9_textlayer.json"

PAT_EFF = re.compile(r"深网和暗网有效情报\s*([\d,]+)\s*份")
PAT_HV = re.compile(r"泄露数据的高价值买卖情报\s*([\d,]+)\s*份")
KEY = "情报"


def variants(page):
    """Every fitz text call, so a divergent number can be attributed to a call."""
    out = {}
    for name, args in (("text", ()), ("blocks", ("blocks",)),
                       ("words", ("words",)), ("dict", ("dict",)),
                       ("rawdict", ("rawdict",)),
                       ("textflags_dehyph", ("text",)),
                       ("textflags_preserve_ws", ("text",))):
        try:
            if name == "text":
                v = page.get_text()
                out[name] = len(v)
            elif name == "textflags_dehyph":
                out[name] = len(page.get_text("text", flags=0))
            elif name == "textflags_preserve_ws":
                out[name] = len(page.get_text("text", flags=4))
            else:
                v = page.get_text(args[0])
                if name == "words":
                    out[name] = len(v)          # N words
                    out["wordchars"] = sum(len(w[4]) for w in v)
                elif name in ("dict", "rawdict"):
                    n = 0
                    for b in v.get("blocks", []):
                        for l in b.get("lines", []):
                            for s in l.get("spans", []):
                                n += len(s.get("text", ""))
                    out[name] = n
                else:
                    out[name] = len(v)
        except Exception as exc:                       # noqa: BLE001
            out[name] = "ERR:%s" % type(exc).__name__
    try:
        out["n_spans"] = sum(
            1 for b in page.get_text("dict").get("blocks", [])
            for l in b.get("lines", []) for _ in l.get("spans", []))
    except Exception:                                  # noqa: BLE001
        out["n_spans"] = None
    return out


def main():
    try:
        import fitz
    except ImportError:
        print("no fitz locally"); return 2
    try:
        import pypdf
    except ImportError:
        pypdf = None

    print("fitz version: %s" % getattr(fitz, "__doc__", "?").splitlines()[0][:70])
    print("fitz __version__: %s" % getattr(fitz, "version", ("?",))[0])
    if pypdf:
        print("pypdf version: %s" % pypdf.__version__)
    print()

    pdfs = sorted(glob.glob(os.path.join(PDFDIR, "*.pdf")))
    out = {"fitz_version": str(getattr(fitz, "version", None)),
           "pypdf_version": getattr(pypdf, "__version__", None) if pypdf else None,
           "per_file": {}}

    for p in pdfs:
        base = os.path.basename(p)
        per = (re.search(r"(\d{4}-\d{2})", base) or [None, None])[1]
        doc = fitz.open(p)
        pages = []
        for i, page in enumerate(doc):
            txt = page.get_text()
            rec = {"page": i + 1, "chars": len(txt)}
            rec.update({("v_" + k): v for k, v in variants(page).items()})
            rec["eff_here"] = bool(PAT_EFF.search(txt))
            rec["hv_here"] = bool(PAT_HV.search(txt))
            rec["key_count"] = txt.count(KEY)
            try:
                imgs = page.get_images(full=True)
                rec["n_images"] = len(imgs)
                area = abs(page.rect.width * page.rect.height) or 1
                cov = 0.0
                for im in page.get_image_info():
                    r = fitz.Rect(im["bbox"])
                    cov += abs(r.width * r.height)
                rec["img_coverage_x_page"] = round(cov / area, 3)
            except Exception:                           # noqa: BLE001
                rec["n_images"] = None
            pages.append(rec)
        total_text = sum(x["chars"] for x in pages)
        total_pypdf = None
        if pypdf is not None:
            try:
                total_pypdf = sum(len((pg.extract_text() or ""))
                                  for pg in pypdf.PdfReader(p).pages)
            except Exception as exc:                    # noqa: BLE001
                total_pypdf = "ERR:%s" % type(exc).__name__
        biggest = max(pages, key=lambda x: x["chars"]) if pages else None
        out["per_file"][per or base] = {
            "file": base,
            "n_pages": len(pages),
            "sum_page_chars": total_text,
            "pypdf_chars": total_pypdf,
            "biggest_text_page": biggest["page"] if biggest else None,
            "biggest_text_page_chars": biggest["chars"] if biggest else None,
            "pages_with_eff": [x["page"] for x in pages if x["eff_here"]],
            "pages_with_hv": [x["page"] for x in pages if x["hv_here"]],
            "pages_with_key": [x["page"] for x in pages if x["key_count"]],
            "key_total": sum(x["key_count"] for x in pages),
            "mean_img_coverage": round(
                sum((x.get("img_coverage_x_page") or 0) for x in pages)
                / max(len(pages), 1), 3),
            "pages": pages,
        }
        d = out["per_file"][per or base]
        print("%s  pages=%d  sum_chars=%-7d pypdf=%-7s biggest=p%d(%d)  "
              "eff@%s hv@%s key=%d imgs=%.2fx"
              % (per, d["n_pages"], d["sum_page_chars"], d["pypdf_chars"],
                 d["biggest_text_page"], d["biggest_text_page_chars"],
                 d["pages_with_eff"], d["pages_with_hv"], d["key_total"],
                 d["mean_img_coverage"]))
        doc.close()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("\nwrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
