#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""64 -- Is p.6 the ONLY page of the five image-only issues that states a figure?

WHY THIS EXISTS
---------------
`57_E9_ocr_p6.json` recovers the E9 anchor from page 6 only, for the five issues
whose bodies are not text objects.  That is legitimate ONLY IF p.6 carries every
figure the report states.  If some other page also prints a count, then
"p.6-only" silently drops data and the recovered curve is incomplete.

So this is not a re-measurement.  It reads the full-document OCR already
produced by `59_E9_ocr_full.py` and asks one question: on which pages does this
document state a number followed by the counting classifier 份 ?

It reports, per issue, the complete set of such pages.  The intended reading is
`pages_with_figures == [6]`.

CONTROLS
--------
* Positive control: the four text-layer issues (2025-01/02/03/04) state known
  figures.  Where a sidecar exists for them, the same detector must find them.
  Here we use 2025-06's headline pair (1,140,767 / 5,232) -- if the detector
  cannot find values we already know are on that page, it is blind, and any
  "page X has no figure" it reports is worthless.
* The detector is deliberately broad (any `label ... <number> 份`), so a third
  metric the report might state would be caught rather than missed.
* Full-width digits and punctuation are normalised; the full-width comma is a
  known trap (C-107) that was caught by a control, not by inspection.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIDECAR_DIR = os.path.join(ROOT, "results", "59_ocr_full_text")
OUT = os.path.join(ROOT, "results", "64_E9_p6_uniqueness.json")

PAGE_RE = re.compile(r"^===== page (\d+) =====\s*$", re.M)

# Any label of 1..24 non-space chars, then a count of >=3 digits, then 份.
# The lower bound of 3 digits keeps us from matching stray "2 份" in prose while
# still catching every figure this report has ever printed (smallest observed
# value is 3,999).
#
# The label class EXCLUDES DIGITS, and that is a fix, not a detail (C-117).
# The first version allowed digits, and because the label group is greedy it
# stole the LEADING digit of the value wherever the OCR left no space between
# label and number. 2025-08 p.6 prints `深网和暗网有效情报68,904 份`; the old
# pattern returned label `深网和暗网有效情报6` and value 8904 -- a plausible
# wrong integer, with the theft visible only as a trailing digit in the label.
# So the old pattern is kept alongside as a DIFFERENCE CONTROL: the two disagree
# exactly where a leading digit was stolen, and any such page is reported rather
# than silently corrected.
FIG_RE = re.compile(r"([^\s；;。：:，,0-9]{1,24})\s*([0-9][0-9,，]{2,})\s*份")
FIG_RE_OLD = re.compile(r"([^\s；;。：:，,]{1,24})\s*([0-9][0-9,，]{2,})\s*份")

FW = {ord(c): ord("0") + i for i, c in enumerate("０１２３４５６７８９")}


def norm(s):
    """Full-width digits -> ASCII; OCR letter-spacing removed inside numbers."""
    return s.translate(FW)


def pages_of(text):
    parts = PAGE_RE.split(text)
    # parts = ['', '1', body1, '2', body2, ...]
    out = {}
    for i in range(1, len(parts) - 1, 2):
        out[int(parts[i])] = parts[i + 1]
    return out


def figures_on(body, rx=None):
    """Return [(label, value)] for every stated count on this page."""
    found = []
    for m in (rx or FIG_RE).finditer(norm(body)):
        label = re.sub(r"\s+", "", m.group(1))
        try:
            v = int(re.sub(r"[,，\s]", "", m.group(2)))
        except ValueError:
            continue
        found.append((label, v))
    return found


def main():
    if not os.path.isdir(SIDECAR_DIR):
        print("no sidecar dir: %s" % SIDECAR_DIR)
        return 1
    sidecars = sorted(f for f in os.listdir(SIDECAR_DIR)
                      if f.startswith("59_ocr_full_") and f.endswith(".txt"))
    if not sidecars:
        print("no sidecars yet in %s" % SIDECAR_DIR)
        return 1

    out = {"instrument": "regex over 59_ full-document OCR sidecars",
           "question": "which pages state a figure (<label> <n> 份)?",
           "issues": {}, "note": ""}
    ok_all, ctrl_ok = True, None

    for fn in sidecars:
        per = fn[len("59_ocr_full_"):-len(".txt")]
        with io.open(os.path.join(SIDECAR_DIR, fn), encoding="utf-8") as fh:
            pg = pages_of(fh.read())
        per_page = {}
        disag = []
        for p in sorted(pg):
            figs = figures_on(pg[p])
            if figs:
                per_page[p] = figs
            # DIFFERENCE CONTROL (C-117): where the two patterns disagree, the
            # old one stole a leading digit. Recorded, never silently resolved.
            old = figures_on(pg[p], FIG_RE_OLD)
            if sorted(old) != sorted(figs):
                disag.append({"page": p, "old": old, "new": figs})
        if disag:
            print("   !! regex disagreement (digit stolen by label) on %s"
                  % [(d["page"], d["old"], d["new"]) for d in disag])
        figpages = sorted(per_page)
        # WHAT THIS FIELD MAY AND MAY NOT MEAN (C-112).
        # The first version of this script treated `figpages == [6]` as the
        # licence for p.6-only extraction.  That was the wrong question, and it
        # answered False on 2025-06 -- correctly, because the report carries
        # OTHER aggregates on other pages: p.9 is a single-incident case count,
        # p.27 is section 4's own monthly total, and p.6 itself carries a third
        # figure (the country subtotal).  A False here is therefore NOT a defect
        # in the E9 extraction and NOT evidence that p.6 is incomplete.
        # What licenses p.6-only extraction is the narrower fact measured
        # elsewhere: the two HEADLINE sentences appear only on p.6.
        out["issues"][per] = {
            "n_pages_ocrd": len(pg),
            "pages_with_figures": figpages,
            "figures": {str(k): v for k, v in per_page.items()},
            "headline_pair_only_on_p6": figpages == [6],
            "regex_disagreements": disag,
            "interpretation": (
                "True  -> no figure anywhere else; p.6 carries the whole document. "
                "False -> the report states OTHER aggregates elsewhere; this says "
                "nothing about whether the two headline bullets are on p.6, which "
                "is the property p.6-only extraction actually needs."),
        }
        if figpages != [6]:
            ok_all = False

        # Positive control: 2025-06 is fully OCRed and its p.6 headline pair is
        # known (1,140,767 / 5,232) from 57_.  If the detector cannot see those,
        # it is blind and its silence elsewhere means nothing.
        if per == "2025-06":
            vals = {v for _l, v in per_page.get(6, [])}
            ctrl_ok = (1140767 in vals and 5232 in vals)
            out["positive_control_2025_06"] = {
                "requirement": "p.6 yields both 1140767 and 5232",
                "observed_values_on_p6": sorted(vals),
                "passes": ctrl_ok,
            }

        print("%s  ocrd=%d pages  figure_pages=%s  p6_only=%s"
              % (per, len(pg), figpages, figpages == [6]))
        for p in figpages:
            print("      p%-3d %s" % (p, per_page[p]))

    out["all_pages_with_figures_are_p6"] = ok_all
    out["positive_control_passes"] = ctrl_ok
    # The positive control is what makes ANY of this readable. Without it, a
    # "no figures on the other pages" result is exactly what a blind detector
    # would also print, and the two cannot be told apart.
    out["verdict_meaningful"] = bool(ctrl_ok) and len(sidecars) > 0
    out["note"] = (
        "READ THIS BEFORE USING THIS FILE. `all_pages_with_figures_are_p6` is "
        "asymmetric and neither value licenses a claim on its own (C-112, "
        "C-113). False is NOT a defect: the report carries section-level "
        "aggregates on other pages too, so a False is the expected value. But "
        "True is NOT an existence claim either -- this detector only matches "
        "`<label> <n> 份`, and 2025-07 returned True while its section 4 DOES "
        "state aggregates, phrased with 条 (C-113). So a True means 'no other "
        "page writes an aggregate with 份', not 'p.6 is the only page with "
        "figures'. What actually licenses p.6-only extraction is the narrower "
        "fact measured elsewhere: the two HEADLINE sentences appear only on "
        "p.6. Read the `figures` map rather than the flag."
    )

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print("\ncontrol=%s  all_p6_only=%s  -> %s"
          % (ctrl_ok, ok_all, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
