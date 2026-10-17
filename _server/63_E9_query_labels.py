#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""63_E9_query_labels.py -- what did each month's report actually COUNT?

C-109 raises the question the E9 anchor's shape forces: the series contains a
12x rise, a repeated month, and a 16x collapse that partially reverses. Before
that shape can be read as the phenomenon, it has to be shown to be a measurement
of one thing -- and the strongest evidence for a change in definition is inside
the reports themselves.

Each report's p.6 carries a screenshot of the publisher's own query UI, with one
category tab highlighted and a result count. If the highlighted CATEGORY changes
across months, then the months are not all counting the same thing, and that is
a source-side fact, not an inference.

It does NOT decide attribution. It reports what the screenshots say and leaves
the inference to whoever writes the claim -- an instrument reports, a person
concludes.

WHAT THIS VERSION FIXES (C-121)
-------------------------------
The first version asked `which_category_matches_bullet` by looking for a number
ADJACENT to each category name. That premise does not hold for these tables:
the OCR renders the category header row and its counts as TWO SEPARATE RUNS,

    代码/文档 数据泄露情报 @ Telegram情报 8人员 0 0 0 6663 0 0 ...

so only the LAST label can bind, and it binds the run's FIRST value (always 0).
The field therefore returned [] for all 9 months -- not because no category
matches, but because the instrument never read a category's count. A consumer
reading [] as "the document says no category matches" would be reading an
absence of measurement as a measurement of absence.

Two further facts that come out of looking at the table properly:

  * The runs have different lengths (8 labels vs 6 values in 2025-01), so a
    label<->value PAIRING IS NOT RECOVERABLE FROM THE TEXT. This script
    therefore reports values by INDEX and never names a category for a value.
  * The single non-zero value is a THIRD QUANTITY -- the selected tab's own
    count -- not the bullet. It coincides with `effective` in some months and
    with `high_value` in others and with NEITHER in 2025-10 (4858), which is
    what proves the coincidence is not identity. In 2025-04 it is 6663 while
    the bullet says 3，999 -- see C-121: that is the mechanism of the C-112
    disagreement, and it is not a second reading of the bullet.

COMPARE RULE
------------
`norm` strips separators on BOTH sides. The original normalised only the tab
side, so a full-width comma in the bullet (03 and 04 write 5，880 / 3，999)
could never match. The coordinator's own first check of this table made the
mirror error -- comparing 96082 against "96,082" and reporting no match for a
value that was present -- which is the same class of defect: the compare rule,
not the data.
"""
import glob
import json
import os
import re
import sys

# argv[1] lets this run off the pod for testing; the pod default is unchanged.
SRC = sys.argv[1] if len(sys.argv) > 1 else "/root/cis/results"
OUT = os.path.join(SRC, "63_E9_query_labels.json")

CATS = ["数据泄露情报", "暗网情报", "Telegram情报", "风险报告", "信息系统",
        "移动端应用", "域名", "邮箱", "代码/文档"]
NUM = r"\d[\d,，]*"
INT_TOKEN = re.compile(r"^\d[\d,，]*$")
YEAR_TOKEN = re.compile(r"^(19|20)\d{2}$")
MONTH_TOKEN = re.compile(r"^\d{1,2}$")

PAIRING_NOTE = ("NOT recoverable from text: the category labels and their counts "
                "are separate OCR runs and the runs differ in length "
                "(2025-01: 8 labels vs 6 values). Values are reported by index; "
                "no category is named for any value.")


def norm(s):
    """Compare rule, applied to BOTH sides. None in -> None out."""
    if s is None:
        return None
    return s.replace("，", "").replace(",", "")


def tab_row_values(flat, labels):
    """The integer run that FOLLOWS the label run, up to the query controls.

    Two stops, both needed: the UI control words terminate the row (2025-04
    otherwise picks up a stray `1` from the zoom/date widget), and a date token
    (4-digit year followed by a 1-2 digit month) terminates it where no control
    word was captured.
    """
    if not labels:
        return []
    last = max(flat.rfind(c) for c in labels)
    if last < 0:
        return []
    tail = flat[last:last + 220]
    cut = len(tail)
    for stop in ("录入时间", "小于等于", "大于等于", "undefined", " X"):
        i = tail.find(stop)
        if i >= 0:
            cut = min(cut, i)
    toks = tail[:cut].split()
    vals = []
    for i, t in enumerate(toks):
        if YEAR_TOKEN.match(t) and i + 1 < len(toks) and MONTH_TOKEN.match(toks[i + 1]):
            break
        if INT_TOKEN.match(t):
            vals.append(t)
    return vals


def routes(flat, present, eff_raw, hv_raw):
    """-> dict. Pure; testable. Reports each route separately, never merged."""
    tab_counts = {}
    for c in present:
        m = re.search(re.escape(c) + r"\s*(" + NUM + r")", flat)
        tab_counts[c] = m.group(1) if m else None

    eff, hv = norm(eff_raw), norm(hv_raw)
    vals = tab_row_values(flat, present)

    # This field used to be called `equals` and to hold `"effective"` /
    # `"high_value"`, which names a SEMANTIC IDENTITY -- "this value IS the
    # effective count" -- on the strength of numeric equality alone. Those are
    # different claims: equality is measured here, identity is not. It now says
    # only what was measured. (Raised in peer review, 2026-09-24.)
    matches = []
    for i, v in enumerate(vals):
        n = norm(v)
        if n and eff is not None and n == eff:
            matches.append({"index": i, "value": v,
                            "equals_numerically": "effective_bullet"})
        elif n and hv is not None and n == hv:
            matches.append({"index": i, "value": v,
                            "equals_numerically": "high_value_bullet"})

    return {
        "tab_counts_adjacent_text": tab_counts,
        "n_categories_with_parsed_adjacent_count":
            sum(1 for v in tab_counts.values() if v),
        "which_category_matches_bullet_adjacent_text": [
            c for c, v in tab_counts.items()
            if norm(v) is not None and norm(v) in (eff, hv) and norm(v)],
        "tab_row_values": vals,
        "tab_row_n_values": len(vals),
        "tab_row_nonzero": [{"index": i, "value": v}
                            for i, v in enumerate(vals) if norm(v) != "0"],
        # Every other cell reads `0`, and nothing on this route witnesses that a
        # 0 is a real zero rather than a digit the OCR dropped or the layout did
        # not print. `0` is also the value most likely to be a sentinel -- a
        # failed `cuDeviceGetCount` reads 0 too (discipline 23, on the GPU
        # probe). So the non-zero list is a count of non-zeros, and must not be
        # read as "the other categories are zero". (Peer review, 2026-09-24.)
        "tab_row_zeros_are_unwitnessed": (
            "the remaining cells read 0; this route does not witness that a 0 is "
            "a real zero rather than a dropped digit. Do not read "
            "`tab_row_nonzero` as `the other categories are zero`."),
        "tab_row_matches": matches,
        "tab_row_pairing": PAIRING_NOTE,
        # The text route is now superseded on its own question. Saying so here
        # keeps a reader from concluding "unanswerable" when it is answered.
        "queried_category": (
            "NOT determined by this route -- the pairing is not recoverable from "
            "text order (see tab_row_pairing). `76_E9_tab_geometry.py` binds each "
            "label to its count by x-geometry on the p.6 pixels, and that is the "
            "route that names the selected category."),
    }


def self_test():
    """The tab-row route must be ABLE to fire, and the adjacency route must be
    shown unable to. A route that has never fired has not been shown to work."""
    cases = [
        # 2025-01, real text: labels then 0 0 0 0 0 96082 then the date controls
        ("应用 域名 邮箱 代码/文档 数据泄露情报 @ Telegram情报 8人员 0 0 0 0 0 96082 "
         "undefined大于等于：2025-01-01 录入时间小于等于：2025-02-01 X",
         ["数据泄露情报", "Telegram情报", "域名", "邮箱", "代码/文档"],
         "96082", "4749", [0, 0, 0, 0, 0, "96082"], "effective_bullet"),
        # 2025-04, real text: the disputed value -- bullet says 3，999, tab row 6663
        ("应用 域名 邮箱 代码/文档 数据泄露情报 @ Telegram情报 8人员 0 0 0 6663 0 0 "
         "录入时间小于等于：2025-05-01 X",
         ["数据泄露情报", "Telegram情报", "域名", "邮箱", "代码/文档"],
         "509,880", "3，999", [0, 0, 0, "6663", 0, 0], None),
    ]
    ok = True
    for flat, present, eff, hv, want_vals, want_eq in cases:
        r = routes(flat, present, eff, hv)
        if r["tab_row_values"] != [str(v) for v in want_vals]:
            print("self-test: tab_row_values %s != %s" % (r["tab_row_values"], want_vals))
            ok = False
        got_eq = (r["tab_row_matches"][0]["equals_numerically"]
                  if r["tab_row_matches"] else None)
        if got_eq != want_eq:
            print("self-test: expected tab_row match=%s, got %s" % (want_eq, got_eq))
            ok = False
        # and the OLD route must be empty on the SAME input -- that is the bug
        if r["which_category_matches_bullet_adjacent_text"]:
            print("self-test: adjacency route fired when it should not have")
            ok = False
    print("self-test: tab-row route fires, adjacency route does not -> %s"
          % ("OK" if ok else "BROKEN"))
    return ok


def main():
    if not self_test():
        print("refusing to emit: the tab-row route has not been shown to fire")
        return 2

    out = {"generated": None, "per_month": {}, "routes": {
        "adjacent_text": "a number immediately after a category name "
                         "(the first version's route; cannot fire on these "
                         "tables -- see module docstring)",
        "tab_row": "the integer run following the label run, reported by INDEX; "
                   "the pairing to a category is " + PAIRING_NOTE}}
    import time
    out["generated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    for f in sorted(glob.glob(os.path.join(SRC, "57_ocr_*_p06.txt"))):
        per = re.search(r"57_ocr_(\d{4}-\d{2})_p06", f)
        per = per.group(1) if per else os.path.basename(f)
        t = open(f, encoding="utf-8").read()
        flat = re.sub(r"\s+", " ", t)

        present = [c for c in CATS if c in flat]
        found = re.search(r"为您找到\s*(" + NUM + r")\s*条匹配结果", flat)
        eff = re.search(r"有效情报\s*(" + NUM + r")\s*份", flat)
        hv = re.search(r"高价值买卖情报\s*(" + NUM + r")\s*份", flat)
        eff_raw = eff.group(1) if eff else None
        hv_raw = hv.group(1) if hv else None

        rec = {"categories_present": present,
               "match_result_line": found.group(1) if found else None,
               "bullet_effective": eff_raw,
               "bullet_high_value": hv_raw,
               "sidecar": f}
        rec.update(routes(flat, present, eff_raw, hv_raw))
        out["per_month"][per] = rec

        print("%s  cats=%s" % (per, present))
        print("     bullets: effective=%s  high_value=%s | match line=%s"
              % (eff_raw, hv_raw, rec["match_result_line"]))
        print("     tab row: %s   nonzero=%s"
              % (rec["tab_row_values"], rec["tab_row_nonzero"]))
        print("     tab row equals a bullet: %s | adjacency route matches: %s "
              "(parsed %d/%d counts)"
              % (rec["tab_row_matches"],
                 rec["which_category_matches_bullet_adjacent_text"],
                 rec["n_categories_with_parsed_adjacent_count"], len(present)))

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
