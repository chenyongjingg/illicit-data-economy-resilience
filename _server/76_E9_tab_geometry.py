#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""76_E9_tab_geometry.py -- bind the p.6 category labels to their counts by
GEOMETRY, not by text order.

WHY GEOMETRY IS THE ONLY ROUTE LEFT. `63_` established that the p.6 table's
label run and value run are separate OCR runs of different lengths (2025-01:
8 labels vs 6 values), so text order cannot pair them, and 63_ therefore reports
values by INDEX and names no category for any value. That is the correct
restraint -- but it leaves the anchor's actual question unanswered:

    do all nine months count the same thing?

The p.6 screenshot marks ONE tab as selected, and that tab's count is the single
non-zero value in the row (63_'s finding). If the non-zero value can be bound to
a labelled column, the label names the queried category, month by month, and the
question becomes answerable from the source instead of by inference.

That binding information is not in the text. It is in the PIXELS: which value
sits under which label. `59_` ran the OCR but kept only the concatenated page
text and discarded the boxes; this tool re-runs rapidocr on the single p.6 of
each issue and KEEPS the boxes.

WHAT THIS TOOL WILL NOT DO
--------------------------
It will not report a pairing the geometry does not support. Where a label has no
value within tolerance, that label gets `null` and is counted in
`n_labels_without_value` -- not silently assigned the nearest thing. An
assignment invented to fill a row would be exactly the defect this project keeps
finding (C-127, C-131).

The raw boxes are emitted alongside the binding so a reader can re-derive the
whole table without trusting the matching step.

INSTRUMENT: rapidocr_onnxruntime on fitz get_pixmap(dpi=200), the same pair as
`59_`, so the token stream is comparable with the full-text OCR already on
record.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = sys.argv[1] if len(sys.argv) > 1 else "/root/cis/data/external/dwcon"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/root/cis/results/76_E9_tab_geometry.json"
PAGE_INDEX = 5                     # p.6, 1-based as the reports number it
DPI = 200
INT_TOKEN = re.compile(r"^\d[\d,，]*$")
CATS = ["数据泄露情报", "暗网情报", "Telegram情报", "风险报告", "信息系统",
        "移动端应用", "域名", "邮箱", "代码/文档"]

# A label and its count are bound only if their x-intervals are close. These
# thresholds are in PIXELS at 200 dpi. They are deliberately generous on the
# vertical axis (the value run may sit a line below the label run) and tight on
# the horizontal one (x is the whole basis of the binding).
MAX_DX = 90.0
MAX_DY = 120.0


_ENGINE = None


def _engine():
    """One RapidOCR instance for the whole run. Constructing it per PDF reloads
    the detection+recognition models nine times; that is minutes of pod CPU spent
    on nothing, on a box that is also running E5p."""
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE


def tokens_for(pdf_path):
    """-> (tokens, page_size). One token per OCR box, with its box and centre."""
    import fitz

    doc = fitz.open(pdf_path)
    if doc.page_count <= PAGE_INDEX:
        return None, None, "page %d absent (n_pages=%d)" % (PAGE_INDEX + 1,
                                                           doc.page_count)
    page = doc[PAGE_INDEX]
    pix = page.get_pixmap(dpi=DPI)
    img = pix.tobytes("png")

    engine = _engine()
    res, _ = engine(img)
    toks = []
    for item in (res or []):
        box, text = item[0], item[1]
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        toks.append({
            "text": text,
            "x0": round(min(xs), 1), "x1": round(max(xs), 1),
            "y0": round(min(ys), 1), "y1": round(max(ys), 1),
            "xc": round((min(xs) + max(xs)) / 2.0, 1),
            "yc": round((min(ys) + max(ys)) / 2.0, 1),
            "is_int": bool(INT_TOKEN.match(text.replace(" ", ""))),
            "is_cat": any(c in text for c in CATS),
        })
    return toks, (pix.width, pix.height), None


def find_rows(toks):
    """Group tokens into horizontal bands by y-centre. Returns rows, each sorted
    by x. Band tolerance is half the median token height, floored at 6 px."""
    if not toks:
        return []
    hs = sorted(t["y1"] - t["y0"] for t in toks)
    med_h = hs[len(hs) // 2] if hs else 12.0
    tol = max(6.0, med_h * 0.5)
    rows, cur = [], []
    for t in sorted(toks, key=lambda z: z["yc"]):
        if cur and t["yc"] - cur[-1]["yc"] > tol:
            rows.append(sorted(cur, key=lambda z: z["xc"]))
            cur = []
        cur.append(t)
    if cur:
        rows.append(sorted(cur, key=lambda z: z["xc"]))
    return rows


def pick_label_row(rows):
    """The row with the most category-name tokens; ties -> the most tokens."""
    best, best_key = None, (-1, -1)
    for i, r in enumerate(rows):
        key = (sum(1 for t in r if t["is_cat"]), len(r))
        if key > best_key:
            best, best_key = i, key
    return best


def pick_value_row(rows, label_idx):
    """The row richest in integers, preferring the label row itself and then the
    nearest row below it (a table's counts sit with or under their headers)."""
    order = []
    if label_idx is not None:
        order.append(label_idx)
        order += [i for i in range(label_idx + 1, len(rows))]
        order += [i for i in range(label_idx - 1, -1, -1)]
    else:
        order = list(range(len(rows)))
    best, best_n = None, -1
    for i in order:
        n = sum(1 for t in rows[i] if t["is_int"])
        if n > best_n:
            best, best_n = i, n
    return best


def bind(labels, values):
    """Nearest-compatible value for each label, or None. Reports the distance and
    the runner-up so a marginal binding is visible rather than asserted."""
    out = []
    for L in labels:
        cands = []
        for V in values:
            dx = abs(V["xc"] - L["xc"])
            dy = abs(V["yc"] - L["yc"])
            if dx <= MAX_DX and dy <= MAX_DY:
                cands.append((dx, dy, V))
        cands.sort(key=lambda c: (c[1], c[0]))
        if not cands:
            out.append({"label": L["text"], "label_xc": L["xc"], "value": None,
                        "dx": None, "dy": None, "runner_up_dx": None,
                        "ambiguous": None, "why": "no value within tolerance"})
            continue
        dx, dy, V = cands[0]
        ru = cands[1][0] if len(cands) > 1 else None
        out.append({
            "label": L["text"], "label_xc": L["xc"],
            "value": V["text"], "value_xc": V["xc"],
            "dx": round(dx, 1), "dy": round(dy, 1),
            "runner_up_dx": (round(ru, 1) if ru is not None else None),
            # marginal if a second candidate is nearly as close: then the
            # geometry does NOT decide, and saying nothing is the honest output
            "ambiguous": bool(ru is not None and (ru - dx) < 8.0),
            "why": None,
        })
    return out


def main():
    pdfs = sorted(glob.glob(os.path.join(SRC, "dwcon_*.pdf")))
    if not pdfs:
        print("no dwcon_*.pdf under %s" % SRC)
        return 3
    print("=" * 78)
    print("76_E9_tab_geometry -- p.6 label<->count binding by x-geometry")
    print("  %d pdfs under %s" % (len(pdfs), SRC))
    print("=" * 78)

    rec = {"instrument": "rapidocr_onnxruntime on fitz get_pixmap(dpi=%d)" % DPI,
           "page": "index %d (p.%d)" % (PAGE_INDEX, PAGE_INDEX + 1),
           "what": ("binds each p.6 category label to its count by x-interval "
                    "proximity; emits the raw boxes so the binding is "
                    "re-derivable without this tool"),
           "tolerances": {"max_dx": MAX_DX, "max_dy": MAX_DY},
           "issues": {}}

    for p in pdfs:
        name = re.search(r"(dwcon_\d{4}-\d{2})", os.path.basename(p))
        key = name.group(1) if name else os.path.basename(p)
        t0 = time.time()
        try:
            toks, size, err = tokens_for(p)
        except Exception as exc:                                  # noqa: BLE001
            print("%-22s ERROR %s: %s" % (key, type(exc).__name__, exc))
            rec["issues"][key] = {"error": "%s: %s" % (type(exc).__name__, exc)}
            continue
        if err:
            print("%-22s %s" % (key, err))
            rec["issues"][key] = {"error": err}
            continue

        rows = find_rows(toks)
        li = pick_label_row(rows)
        vi = pick_value_row(rows, li)
        labels = [t for t in (rows[li] if li is not None else []) if t["is_cat"]]
        values = [t for t in (rows[vi] if vi is not None else []) if t["is_int"]]
        bnd = bind(labels, values)

        nz = [v for v in values if v["text"].replace(",", "").replace("，", "") != "0"]
        rec["issues"][key] = {
            "pdf": os.path.basename(p),
            "page_size": size,
            "seconds": round(time.time() - t0, 1),
            "n_tokens": len(toks),
            "n_rows": len(rows),
            "label_row_index": li, "value_row_index": vi,
            "n_labels": len(labels), "n_values": len(values),
            "labels": [{"text": t["text"], "xc": t["xc"], "y0": t["y0"]}
                       for t in labels],
            "values": [{"text": t["text"], "xc": t["xc"], "y0": t["y0"]}
                       for t in values],
            "tab_row_binding": bnd,
            "n_labels_without_value": sum(1 for b in bnd if b["value"] is None),
            "n_ambiguous": sum(1 for b in bnd if b["ambiguous"]),
            "nonzero_values": [{"text": v["text"], "xc": v["xc"]} for v in nz],
            "nonzero_bound_to": [
                b["label"] for b in bnd
                if b["value"] is not None
                and b["value"].replace(",", "").replace("，", "") != "0"],
            "all_rows": [{"y": round(r[0]["yc"], 1),
                          "texts": [t["text"] for t in r]} for r in rows],
        }
        print("%-22s rows=%-3d labels=%-3d values=%-3d nz=%d  bound_to=%s"
              % (key, len(rows), len(labels), len(values), len(nz),
                 rec["issues"][key]["nonzero_bound_to"]))
        for b in bnd:
            print("      %-14s xc=%-7.1f -> %-8s dx=%-6s dy=%-6s%s"
                  % (b["label"][:14], b["label_xc"], b["value"], b["dx"],
                     b["dy"], "  AMBIGUOUS" if b["ambiguous"] else ""))
        sys.stdout.flush()

    ok = [k for k, v in rec["issues"].items() if "error" not in v]
    rec["n_issues_bound"] = len(ok)
    rec["summary"] = {
        "issues_with_geometry": len(ok),
        "issues_where_nonzero_is_bound": sum(
            1 for k in ok if rec["issues"][k]["nonzero_bound_to"]),
        "issues_with_unbound_labels": [k for k in ok
                                       if rec["issues"][k]["n_labels_without_value"]],
        "issues_with_ambiguous_binding": [k for k in ok
                                          if rec["issues"][k]["n_ambiguous"]],
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    print("\nsummary: %s" % json.dumps(rec["summary"], ensure_ascii=False))
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
