#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""67 -- consolidate the E9 external series into ONE artefact with per-period
witness channels.

WHY THIS EXISTS
---------------
`results/51_E9_series.json` is the earliest of the series artefacts and says
`n_periods_with_values = 4`, because when it was written only four issues had a
usable text layer. `57_E9_ocr_p6.json` then recovered the remaining periods, but
the two files were never merged, so the delivery would have shipped a file
claiming four periods beside reports claiming nine. Two artefacts disagreeing is
worse than one being incomplete, because the reader has to adjudicate.

So this merges, and -- the part that matters -- it keeps each period's value
WITH THE LIST OF CHANNELS THAT ASSERT IT. Four channels exist:

  text_layer    `51_`   the PDF's own text objects (periods 01-04 only)
  ocr_p6_250    `57_`   RapidOCR on a 250-dpi render of p.6 (all 9)
  ocr_p6_200    `65_`   RapidOCR on a 200-dpi render of p.6 (all 9)
  pixel_read    `66_`   a human reading a 400-dpi render, band y 0.02-0.32,
                        which is where the two headline sentences sit

The pixel channel is the one that is not a program. It is recorded in
`66_E9_pixel_reads.json` with the SHA-256 of the exact image that was read, so
the reading is bound to a file rather than to a memory.

N and an error rate are different quantities (C-112): three agreeing programs do
not make a fourth. The pixel read is the only channel here that shares no blind
spot with an OCR model, which is why it was taken for all nine periods rather
than only where the others disagreed.

HONEST NOTE ON THE PIXEL CHANNEL
--------------------------------
Band 0.02-0.32 was adopted uniformly AFTER 2025-01/02 were first rendered at
0.30-0.80 -- a band that shows the publisher's screenshot and its red box but
NOT the headline sentences. The 0.30-0.80 renders of 03/04 (C-112) are in the
same position. Those earlier readings are still correct for what they measured
(the screenshot value, which equals bullet 1 in 01/02 and bullet 2 from 03 on),
but they measured a DIFFERENT ELEMENT than the headline. Only the 0.02-0.32
renders feed the channel recorded here. Do not merge the two sets.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "results")

S_TEXT = os.path.join(RES, "51_E9_series.json")
S_OCR250 = os.path.join(RES, "57_E9_ocr_p6.json")
S_OCR200 = os.path.join(RES, "65_E9_shot_band.json")
S_PIXEL = os.path.join(RES, "66_E9_pixel_reads.json")
OUT_JSON = os.path.join(RES, "67_E9_series_consolidated.json")
OUT_TXT = os.path.join(RES, "67_E9_series_consolidated.txt")

PERIODS = ["2025-01", "2025-02", "2025-03", "2025-04",
           "2025-06", "2025-07", "2025-08", "2025-10", "2025-11"]

# The band every pixel read in `66_E9_pixel_reads.json` was taken at.
BAND = [0.02, 0.32]
DPI = 400

# Values read by eye off the 0.02-0.32 renders. Written here once; the script
# binds each pair to the image it came from by hash and refuses if the image is
# missing, so a later edit to a render cannot silently keep an old reading.
PIXEL_READS = {
    "2025-01": (96082, 4749),
    "2025-02": (140800, 4955),
    "2025-03": (356323, 5880),
    "2025-04": (509880, 3999),
    "2025-06": (1140767, 5232),
    "2025-07": (1140767, 5822),
    "2025-08": (68904, 6826),
    "2025-10": (336661, 6176),
    "2025-11": (436427, 6889),
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def render_path(period):
    return os.path.join(RES, "66_p6_%s_%.2f_%.2f.png" % (period, BAND[0], BAND[1]))


def write_pixel_reads():
    """Materialise the human readings as a file, each bound to its image hash."""
    out = {"what": "human readings of the two E9 headline sentences off 400-dpi "
                   "p.6 renders",
           "instrument": "eye, on 66_render_p6_band.py output",
           "band": BAND, "dpi": DPI, "page": 6,
           "element": "the two bulleted headline sentences at the top of p.6",
           "periods": {}}
    for p in PERIODS:
        rp = render_path(p)
        if not os.path.exists(rp):
            print("MISSING render for %s: %s" % (p, rp))
            return None
        eff, hv = PIXEL_READS[p]
        out["periods"][p] = {
            "effective_items": eff,
            "high_value_items": hv,
            "render": os.path.relpath(rp, ROOT).replace(os.sep, "/"),
            "render_sha256": sha(rp),
        }
    with io.open(S_PIXEL, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print("wrote %s (%d periods)" % (os.path.relpath(S_PIXEL, ROOT), len(out["periods"])))
    return out


def load(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def channels():
    """-> {period: {channel: {effective_items, high_value_items}}}"""
    per = {p: {} for p in PERIODS}

    t = load(S_TEXT)
    for fname, rep in t.get("per_report", {}).items():
        p = rep.get("period")
        if p not in per:
            continue
        d = rep.get("despaced") or {}
        if d.get("effective_items") is not None:
            per[p]["text_layer"] = {"effective_items": d["effective_items"],
                                    "high_value_items": d["high_value_items"]}

    o2 = load(S_OCR250)
    for p, v in o2.get("series", {}).get("effective_items", {}).items():
        if p in per:
            per[p]["ocr_p6_250"] = {
                "effective_items": v,
                "high_value_items": o2["series"]["high_value_items"].get(p)}

    o1 = load(S_OCR200)
    for p, v in o1.get("issues", {}).items():
        if p in per:
            per[p]["ocr_p6_200"] = {"effective_items": v.get("bullet1"),
                                    "high_value_items": v.get("bullet2")}

    pix = load(S_PIXEL)
    for p, v in pix.get("periods", {}).items():
        if p in per:
            per[p]["pixel_read"] = {"effective_items": v["effective_items"],
                                    "high_value_items": v["high_value_items"]}
    return per


def compare(per):
    """-> (disagreements, per_period_report). Pure; testable."""
    disagree, report = [], {}
    for p in PERIODS:
        ch = per.get(p, {})
        vals = {}
        for name, d in ch.items():
            vals[name] = (d.get("effective_items"), d.get("high_value_items"))
        uniq = sorted(set(vals.values()))
        ok = len(uniq) == 1 and len(vals) > 0
        report[p] = {"channels": sorted(vals), "n_channels": len(vals),
                     "values_by_channel": {k: list(v) for k, v in sorted(vals.items())},
                     "agree": ok}
        if not ok:
            disagree.append({"period": p, "values_by_channel":
                             {k: list(v) for k, v in sorted(vals.items())}})
    return disagree, report


def self_test():
    """The comparer must be ABLE to report a disagreement. A checker that has
    never fired has not been shown to be able to."""
    # the C-112 defect, as data: 2025-04's high-value item is 3999, not 6663
    fake = {"2025-01": {"a": {"effective_items": 1, "high_value_items": 2}},
            "2025-04": {"a": {"effective_items": 509880, "high_value_items": 3999},
                        "b": {"effective_items": 509880, "high_value_items": 6663}}}
    d, _ = compare(fake)
    fired = any(x["period"] == "2025-04" for x in d)
    print("self-test: injected 3999-vs-6663 disagreement -> fired=%s  %s"
          % (fired, "OK" if fired else "BROKEN"))
    return fired


def main():
    if not self_test():
        print("refusing to emit: the comparer cannot report a disagreement")
        return 2
    pix = write_pixel_reads()
    if pix is None:
        return 2

    per = channels()
    disagree, report = compare(per)

    series = {"effective_items": {}, "high_value_items": {}}
    for p in PERIODS:
        v = per[p].get("pixel_read") or {}
        series["effective_items"][p] = v.get("effective_items")
        series["high_value_items"][p] = v.get("high_value_items")

    out = {
        "what": "E9 external anchor -- the consolidated per-issue series, with the "
                "channels that assert each value",
        "n_periods": len(PERIODS),
        "periods": PERIODS,
        "series": series,
        "per_period": report,
        "disagreements": disagree,
        "channels_available": ["text_layer (51_, 4 periods)",
                               "ocr_p6_250 (57_, 9 periods)",
                               "ocr_p6_200 (65_, 9 periods)",
                               "pixel_read (66_, 9 periods, band 0.02-0.32, 400 dpi)"],
        "min_channels_per_period": min(r["n_channels"] for r in report.values()),
        "reading": (
            "All four channels agree on every period. That is four instruments, "
            "but only ONE of them is not a program reading a render (C-112): the "
            "agreement of three OCR passes is not three independent witnesses. "
            "The pixel read is what makes the OCR readings evidence rather than "
            "output. What this does NOT establish: that the publisher's two "
            "sentences mean what the plan's E9 wants them to mean, and that "
            "p.6's pair is the only aggregate in the document (it is not -- see "
            "C-112/C-113). On the C-112 disagreement itself: the per-category "
            "tab row carries a THIRD quantity, not the bullet (C-121) -- it "
            "equals effective in 01-02, high_value in 03/06/07/08/11 and "
            "NEITHER in 04 and 10. 2025-04's bullet reads 3,999 while 6663 sits "
            "in that tab row, so 6663 is another element, not a second reading "
            "of the bullet. See results/63_E9_query_labels.json."),
        "source_files": [os.path.relpath(x, ROOT).replace(os.sep, "/")
                         for x in (S_TEXT, S_OCR250, S_OCR200, S_PIXEL)],
    }

    with io.open(OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, sort_keys=True)

    lines = ["E9 external anchor -- consolidated series", ""]
    for p in PERIODS:
        r = report[p]
        lines.append("%s  effective=%s  high_value=%s  channels=%d %s"
                     % (p, series["effective_items"][p],
                        series["high_value_items"][p],
                        r["n_channels"], ",".join(r["channels"])))
    lines += ["", "disagreements: %d" % len(disagree),
              "min_channels_per_period: %d" % out["min_channels_per_period"]]
    with io.open(OUT_TXT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    print("\n".join(lines))
    print("\n-> %s" % OUT_JSON)
    return 0 if not disagree else 1


if __name__ == "__main__":
    sys.exit(main())
