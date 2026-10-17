#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""77_E5p_arm_table.py -- the deliverable table E5 actually promises.

The plan says, verbatim, that E5's output is `表：TGN vs 基线 AUC`. So the
question E5 exists to answer is COMPARATIVE: does the temporal GNN beat
GraphSAGE and the MLP feature baseline? `75_E5p_verify.py` does not answer that
-- it asks whether each arm clears the no-skill floor, which is a different
(and weaker) question. A pipeline can pass every admissibility check while the
headline model is not better than a baseline, and the honest report has to be
able to say so.

TWO METRICS, SHOWN SIDE BY SIDE, NEVER BLENDED
----------------------------------------------
`auc_test` is POOLED across entry steps; `within_t0_auc.weighted` conditions on
the entry step, removing the calendar. They are different quantities and the
gap between them IS the calendar component (the report's section 5 says this).
This tool prints both, labels both, and refuses to pick one silently -- choosing
the published field is a decision that belongs in the report, with the control
stated on the same scale (G-72 / peer R62).

WHAT IT WILL NOT DO
-------------------
It does not declare a winner. It prints differences and, where a comparison is
asked for, prints both orderings' margins so that "TGN wins" and "TGN does not
win" are equally visible. If a baseline is within noise of the headline model,
the table must show that rather than a bolded maximum.

Usage: 77_E5p_arm_table.py [artefact.json] [--md out.md]
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT = r"D:\CIS\results\53_E5p_result.json"
DELTAS = ("1", "3", "5")
ARMS = ("mlp_feature_only", "graphsage", "tgn")
LABEL = {"mlp_feature_only": "MLP (feature baseline)",
         "graphsage": "GraphSAGE",
         "tgn": "TGN (headline)"}


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def fmt(v, w=8):
    return ("%*.4f" % (w, v)) if num(v) else ("%*s" % (w, "n/a"))


def get(arm, D):
    by = ((arm or {}).get("by_delta") or {}).get(D) or {}
    w = (by.get("within_t0_auc") or {}).get("weighted")
    return by.get("auc_test"), w, by.get("n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else DEFAULT
    out_md = None
    if "--md" in sys.argv:
        out_md = sys.argv[sys.argv.index("--md") + 1]

    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    emit("=" * 88)
    emit("77_E5p_arm_table -- E5 deliverable: TGN vs baselines, BOTH metrics")
    emit("  target: %s" % path)
    emit("=" * 88)

    if not os.path.exists(path):
        emit("\nABSENT: no file at that path. Statement about the filesystem,")
        emit("        NOT about the experiment.")
        return 3
    try:
        with io.open(path, encoding="utf-8") as fh:
            r = json.load(fh)
    except Exception as exc:                                   # noqa: BLE001
        emit("\nUNPARSEABLE (%s) -- cannot build a table." % type(exc).__name__)
        return 3

    arms = r.get("arms") or {}
    ctl = ((r.get("leakage_check") or {}).get("shuffled_label_control") or {})
    ctl_w = {D: (v or {}).get("weighted")
             for D, v in (ctl.get("test_within_t0_auc_by_delta") or {}).items()}
    ctl_p = ctl.get("test_auc_by_delta") or {}

    emit()
    emit("TABLE 1 -- per arm, per delta. 'pooled' is the calendar-confounded")
    emit("           number; 'within-t0' is the one the arms are JUDGED on.")
    emit()
    emit("%-24s %-4s %10s %12s %8s %12s" %
         ("arm", "delta", "pooled", "within-t0", "n", "ctrl(with-t0)"))
    emit("-" * 88)
    have_any = False
    for name in ARMS:
        for D in DELTAS:
            p, w, n = get(arms.get(name), D)
            have_any = have_any or num(p) or num(w)
            emit("%-24s %-4s %s %s %8s %s" %
                 (LABEL.get(name, name), D, fmt(p, 10), fmt(w, 12),
                  str(n) if isinstance(n, int) else "n/a", fmt(ctl_w.get(D), 12)))
    if not have_any:
        emit("\nNO arm carries any AUC at any delta -- nothing to tabulate.")
        emit("        Statement about the RECORD. Report neither a win nor a loss.")
        return 3

    emit()
    emit("  control (within-t0): %s" %
         {D: (round(v, 5) if num(v) else v) for D, v in ctl_w.items()})
    emit("  control (pooled)   : %s   <- NOT the band's scale" %
         {D: (round(v, 5) if num(v) else v) for D, v in ctl_p.items()})

    # ---- the comparative question the plan actually asks --------------------
    emit()
    emit("TABLE 2 -- HEADLINE vs EACH BASELINE, on within-t0 (the judged metric).")
    emit("           A positive delta means TGN is higher. Both directions are")
    emit("           printed; this tool does not call a winner.")
    emit()
    emit("%-32s %-5s %12s %12s %10s" % ("comparison", "delta", "TGN", "baseline",
                                        "TGN - base"))
    emit("-" * 88)
    tgn = arms.get("tgn")
    for base in ("graphsage", "mlp_feature_only"):
        for D in DELTAS:
            _, tw, _ = get(tgn, D)
            _, bw, _ = get(arms.get(base), D)
            d = (tw - bw) if (num(tw) and num(bw)) else None
            emit("%-32s %-5s %s %s %s" %
                 ("TGN vs " + LABEL.get(base, base), D, fmt(tw, 12), fmt(bw, 12),
                  ("%10.4f" % d) if num(d) else "%10s" % "n/a"))

    emit()
    emit("READ THIS BEFORE QUOTING ANY CELL")
    emit("  * A higher within-t0 AUC is better. Differences below the control's")
    emit("    own sampling spread are not differences (see 76_E5p_null_band.py).")
    emit("  * The plan's deliverable is 'TGN vs baseline AUC'. If TGN does not")
    emit("    exceed a baseline, THAT is the result and must be reported as the")
    emit("    result -- not omitted, and not replaced by the pooled column,")
    emit("    which is the larger number for every arm here.")
    emit("  * The checkpoint was selected on the POOLED validation AUC (G-72),")
    emit("    so the within-t0 cell is not the best-of-epochs for its own metric.")

    if out_md:
        with io.open(out_md, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        print("\n[md] wrote %s" % out_md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
