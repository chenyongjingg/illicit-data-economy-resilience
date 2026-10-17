#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""51_E9_series_extract.py -- pull the series out of the 9 DWC reports. (v2)

v1 WAS WRONG IN TWO WAYS, both mine, both recorded rather than quietly fixed:

  (1) It reported `scalars: None` for all 9 issues. That was not a finding about
      the documents. `read_text()` returns only {fitz_chars, pypdf_chars,
      _text, *_error} -- it does NOT return effective_items/high_value_items,
      because those are computed by `extract()`. v1 read the wrong dict and then
      printed the missing keys as if the documents had yielded nothing. Reading a
      field that does not exist and reporting its absence as an absence in the
      object is the same error this project keeps meeting.

  (2) Every pattern scored 0 because the PDF text layer breaks digits across
      lines and spaces: the reports render "2025年1月" as "202\n5 年\n1 月" and
      "4,749" as "4 ,749". Patterns written against clean text cannot match.

WHAT v2 DOES
    * calls M.extract() -- the same function 43_ used, so the scalars are
      comparable rather than re-derived by different code
    * searches BOTH the raw text and a digit-despaced normalisation, and says
      which one matched
    * reports, per issue, exactly what was and was not found
    * dumps the text layer of every issue as a sidecar so the extraction is
      auditable without re-downloading 135 MiB

    A scalar the document does not yield is recorded as None. It is never
    interpolated, and the series is never completed by assumption.
"""
import glob
import importlib.util
import json
import os
import re
import sys
import time

spec = importlib.util.spec_from_file_location(
    "e9anchor", "/root/cis/scripts/42_E9_anchor_dwcon.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

PDFDIR = "/root/cis/data/external/dwcon"
OUTDIR = "/root/cis/results"
RES = os.path.join(OUTDIR, "51_E9_series.json")
TXT = os.path.join(OUTDIR, "51_E9_series.txt")


def despaced(t):
    """Collapse whitespace that sits inside a number: '4 ,749' -> '4,749',
    '202\\n5' -> '2025'. Only touches gaps between digits/commas, so ordinary
    word spacing is left alone."""
    t = re.sub(r"(?<=\d)\s+(?=[\d,])", "", t)
    t = re.sub(r"(?<=,)\s+(?=\d)", "", t)
    return t


def main():
    pdfs = sorted(glob.glob(os.path.join(PDFDIR, "*.pdf")))
    os.makedirs(OUTDIR, exist_ok=True)
    print("PDFs: %d" % len(pdfs))

    per, series_eff, series_hv = {}, {}, {}
    for p in pdfs:
        base = os.path.basename(p)
        period = (re.search(r"(\d{4}-\d{2})", base) or [None, None])[1]
        print("\n=== %s ===" % base)

        # Same call 43_ made -> comparable values.
        ex = M.extract(p)
        t = M.read_text(p).get("_text") or ""
        tn = despaced(t)

        side = os.path.join(OUTDIR, "51_e9_text_%s.txt" % (period or base))
        with open(side, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(t)

        raw_hits = {"effective_items": M.PAT_EFFECTIVE.search(t) is not None,
                    "high_value_items": M.PAT_HIGHVALUE.search(t) is not None}
        nrm_hits = {"effective_items": M.PAT_EFFECTIVE.search(tn) is not None,
                    "high_value_items": M.PAT_HIGHVALUE.search(tn) is not None}
        # Values re-derived on the despaced text, which is the stricter read.
        eff_n = M.PAT_EFFECTIVE.search(tn)
        hv_n = M.PAT_HIGHVALUE.search(tn)
        eff_v = int(eff_n.group(1).replace(",", "")) if eff_n else None
        hv_v = int(hv_n.group(1).replace(",", "")) if hv_n else None

        print("   text %d chars (despaced %d)" % (len(t), len(tn)))
        print("   extract(): period=%s eff=%s hv=%s"
              % (ex.get("stated_period"), ex.get("effective_items"),
                 ex.get("high_value_items")))
        print("   despaced : eff=%s hv=%s" % (eff_v, hv_v))

        # WITNESS -- separates "the document states no such number" from "my
        # pattern does not fit this layout". Both currently land on None, which
        # makes a matcher that stopped matching indistinguishable from a report
        # that carries no scalar. Recording whether numbers sit next to the
        # keyword is the cheap thing that tells them apart.
        wit = {}
        for kw in ("有效情报", "高价值买卖情报"):
            i = tn.find(kw)
            if i < 0:
                wit[kw] = {"keyword_present": False}
            else:
                win = tn[i:i + 160]
                wit[kw] = {"keyword_present": True,
                           "numbers_near": re.findall(r"\d[\d,]{2,}", win),
                           "window": win[:110]}
        for kw, w in wit.items():
            print("   witness %-10s present=%s numbers_near=%s"
                  % (kw, w["keyword_present"], w.get("numbers_near")))
        if eff_v is not None and ex.get("effective_items") not in (None, eff_v):
            print("   !! DISAGREE raw=%s despaced=%s"
                  % (ex.get("effective_items"), eff_v))

        for label, v in (("effective_items", eff_v), ("high_value_items", hv_v)):
            if v is not None:
                (series_eff if label == "effective_items" else series_hv)[
                    period or base] = v

        per[base] = {"period": period, "text_chars": len(t), "sidecar": side,
                     "extract_raw": {"stated_period": ex.get("stated_period"),
                                     "effective_items": ex.get("effective_items"),
                                     "high_value_items": ex.get("high_value_items")},
                     "despaced": {"effective_items": eff_v,
                                  "high_value_items": hv_v},
                     "pattern_found_raw": dict(raw_hits),
                     "pattern_found_despaced": dict(nrm_hits),
                     "witness": wit}

    series = {"effective_items": series_eff, "high_value_items": series_hv}
    n_periods = len(set(list(series_eff) + list(series_hv)))
    payload = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "what": "E9 external anchor -- per-issue series values, re-derived",
        "n_pdfs": len(pdfs),
        "n_periods_with_values": n_periods,
        "note": ("values are per-ISSUE headline counts read from the PDF TEXT LAYER, which exists for 4 of 9 issues only (text_chars 11,889-12,967 for 2025-01..04 vs 5,303-5,861 for 2025-06..11); the 2025-06..11 headline numbers are present in results/59_ocr_full_text/. The per-issue declared window is measured in results/71_E9_query_windows.json and was re-checked directly against the page-6 OCR: the UPPER bound is readable on all 9 issues and equals the first day of the month AFTER the issue's own month on 8 of them; 2025-10 is the single exception (lower 2025-09-01, upper 2025-10-01) so its window covers September, not October. The LOWER bound is not recoverable from OCR for 2025-03/04/11, so 'unread' applies to that bound on those three issues, not to their windows. This series is NOT attested as a like-for-like monthly series; read both files before treating it as one."),
        "series": series,
        "per_report": per,
    }
    with open(RES, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    with open(TXT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("E9 series -- per-issue\n\n")
        fh.write("%-18s %-14s %-14s\n" % ("period", "effective", "high_value"))
        for k in sorted(set(list(series_eff) + list(series_hv))):
            fh.write("%-18s %-14s %-14s\n" % (k, series_eff.get(k, "-"),
                                              series_hv.get(k, "-")))
    print("\n=== SERIES ===")
    for k in sorted(set(list(series_eff) + list(series_hv))):
        print("   %-10s eff=%-10s hv=%-8s"
              % (k, series_eff.get(k, "-"), series_hv.get(k, "-")))
    print("periods with any value: %d / %d pdfs" % (n_periods, len(pdfs)))
    print("wrote %s" % RES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
