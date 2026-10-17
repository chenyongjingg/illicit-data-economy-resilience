#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""76_E5p_null_band.py -- the null band for `within_t0_auc`, derived from the
bin STRUCTURE, never from the control's scores.

WHY THIS EXISTS
---------------
`75_E5p_verify.py` tests the shuffled-label control's within-t0 reading against a
hard-coded `abs(v - 0.5) < 0.05`. That 0.05 was written by hand and had no
empirical basis. A peer objected, correctly, that a band must come from the
control's own null rather than from a constant -- but their stated mechanism
(that a POOLED floor sits above 0.5) no longer applies, because the band was
moved onto the within-t0 metric, where 0.5 is the null by construction.

What survives of their objection is the SAMPLING part. `within_t0_auc` is a
size-weighted mean of per-bin AUCs, and `auc()` returns None for any bin holding
only one class -- those bins are SKIPPED. If entry steps shatter into many thin
single-class bins, the effective sample size collapses and a genuinely blind
control can land outside +-0.05 through sampling error alone. So the band's
adequacy is itself a measurable question, and this measures it.

WHY IT NEEDS NO DATASET
-----------------------
`within_t0_auc` returns `per_bin[t] = [n_rows, auc, n_pos, pos_rate]`, so the
landed artefact already carries the bin structure. Under H0 the per-bin AUC has
Mann-Whitney variance

        Var_t = (n_t + 1) / (12 * n_pos_t * n_neg_t)

and the weighted mean W = sum(w_t * a_t) / sum(w_t) with w_t = n_t has

        Var(W) = sum(w_t^2 * Var_t) / (sum(w_t))^2

which uses only counts and class balance -- properties of the LABELS, not of the
model. So the band is computable without reloading the data, and `auc` is
dropped on read: the one number this tool must not look at is the one it is
judging.

FIVE OUTCOMES, FIVE EXIT CODES (same convention as 75_)
    0  every delta assessed, and the reading is inside the derived null band
    2  assessed, and OUTSIDE -- the control is genuinely off-chance, not noisy
    3  ABSENT / unparseable / nothing derivable at all: says nothing about science
    4  INCOMPLETE -- inside where it could be assessed, but some delta has no
       per_bin to derive from, so that delta was never assessed
    5  OUTSIDE at some delta AND unassessed at another: both, neither subordinate

Codes 3/4/5 matter: "the control is off-chance", "I could not derive a band", and
"some deltas were never looked at" must never share a return value. A code is the
one channel a caller cannot read selectively -- returning 0 while a delta is
missing would tell a code-only consumer "the control is at chance" about a delta
this tool never examined.

    6  BAD INVOCATION -- the command line itself was wrong, so nothing was read.

Code 6 is separate for the same reason 3 is separate from 0: "my instrument was
never aimed" and "the object is absent" are different facts about the world, and
folding them together is how a tool that never ran gets read as a measurement.
An unknown `--option` is code 6, not a shrug.

`--json <path>` writes the whole reading -- bands, per-delta verdicts, the
target's own sha256, and the exit code -- as one JSON object, at EVERY exit
including the failing ones, so a caller can tell "the target was absent" from
"the tool never ran". The write is `newline="\n"`: the record is consumed by
POSIX tools, and the line ending is part of the record.

Usage: 76_E5p_null_band.py <artefact.json> [--draws 4000] [--json out.json]
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT = r"D:\CIS\results\53_E5p_result.json"
DELTAS = ("1", "3", "5")
Z99 = 2.5758293035489004          # two-sided 99%


def weighted_null_se(per_bin):
    """Analytic null SE of the size-weighted mean AUC, from counts alone.

    `per_bin` values are [n_rows, auc, n_pos, pos_rate]. The auc is deliberately
    not unpacked -- the band must not see it.
    """
    num = 0.0
    den = 0.0
    bins = 0
    skipped = 0
    for _t, rec in (per_bin or {}).items():
        if not isinstance(rec, (list, tuple)) or len(rec) < 3:
            skipped += 1
            continue
        n = rec[0]
        n_pos = rec[2]
        if not isinstance(n, int) or not isinstance(n_pos, int):
            skipped += 1
            continue
        n_neg = n - n_pos
        if n <= 0 or n_pos <= 0 or n_neg <= 0:
            # exactly the bins `auc()` skipped: one class only, contributes nothing
            skipped += 1
            continue
        w = float(n)
        var_t = (n + 1.0) / (12.0 * n_pos * n_neg)
        num += w * w * var_t
        den += w
        bins += 1
    if bins == 0 or den == 0.0:
        return None, 0, skipped
    return math.sqrt(num / (den * den)), bins, skipped


def mc_band(per_bin, draws, seed=20260924):
    """Monte-Carlo band: draw each bin's AUC from N(0.5, Var_t) and reweight.

    The analytic SE above assumes the bins are independent and their AUCs
    approximately normal, which is optimistic when a bin is small (an AUC from
    n_pos=3, n_neg=4 is a coarse lattice, not a normal). This resamples the same
    variance model, so it checks the SHAPE of the null rather than assuming it --
    but it inherits the same independence assumption, and that is stated rather
    than hidden.
    """
    import random
    rnd = random.Random(seed)
    bins = []
    for _t, rec in (per_bin or {}).items():
        if not isinstance(rec, (list, tuple)) or len(rec) < 3:
            continue
        n, n_pos = rec[0], rec[2]
        if not isinstance(n, int) or not isinstance(n_pos, int):
            continue
        n_neg = n - n_pos
        if n <= 0 or n_pos <= 0 or n_neg <= 0:
            continue
        bins.append((float(n), math.sqrt((n + 1.0) / (12.0 * n_pos * n_neg))))
    if not bins:
        return None
    tot = sum(w for w, _ in bins)
    ws = []
    for _ in range(draws):
        acc = 0.0
        for w, sd in bins:
            acc += w * rnd.gauss(0.5, sd)
        ws.append(acc / tot)
    ws.sort()
    lo = ws[int(0.005 * draws)]
    hi = ws[min(int(0.995 * draws), draws - 1)]
    return lo, hi


OUT_PATH = None                   # set from --json; None means "do not write"


def parse_args(argv):
    """Split positionals from options, refusing to swallow what it cannot use.

    The defect this replaces: `--json` was advertised in the usage line and never
    implemented, and every `--flag` was stripped by a filter, so the output path
    fell through as a second positional and was silently ignored -- a promise
    made by the documentation and broken by the code. An option this tool does
    not know is now an error.
    """
    positional = []
    opts = {"draws": 4000, "json": None}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--draws", "--json"):
            if i + 1 >= len(argv):
                raise ValueError("%s needs a value" % a)
            if a == "--draws":
                opts["draws"] = int(argv[i + 1])
                if opts["draws"] <= 0:
                    raise ValueError("--draws must be positive")
            else:
                opts["json"] = argv[i + 1]
            i += 2
            continue
        if a.startswith("--"):
            raise ValueError("unknown option %r" % a)
        positional.append(a)
        i += 1
    if len(positional) > 1:
        raise ValueError("at most one artefact path; got %d" % len(positional))
    return positional, opts


def emit(payload):
    """Write the machine-readable record, if one was asked for. Never raises.

    Called at EVERY exit, including the failing ones. A caller who asked for a
    file and did not get one must be able to tell "the object was absent" from
    "the tool never ran"; the payload carries `state` and `exit_code` so that
    question is answerable without reading the terminal.
    """
    if not OUT_PATH:
        return
    payload.setdefault("tool", "76_E5p_null_band.py")
    payload["exit_code"] = payload.get("exit_code")
    try:
        d = os.path.dirname(os.path.abspath(OUT_PATH))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        # newline="\n" is explicit: the record is consumed by POSIX tools and by
        # `sha256sum -c`, and the line ending is part of the record.
        with io.open(OUT_PATH, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(payload, indent=2, sort_keys=True,
                                ensure_ascii=False))
            fh.write("\n")
    except Exception as exc:                                  # noqa: BLE001
        # The file is a convenience; the exit code is the contract. Say so
        # loudly rather than letting a failed write masquerade as a quiet run.
        print("WARNING: could not write --json %s (%s: %s)"
              % (OUT_PATH, type(exc).__name__, exc))


def finish(payload, code):
    """Set the code on the payload, write it, and return the code."""
    payload["exit_code"] = code
    emit(payload)
    return code


def main():
    global OUT_PATH
    try:
        positional, opts = parse_args(sys.argv[1:])
    except ValueError as exc:
        print("BAD INVOCATION: %s" % exc)
        print("usage: 76_E5p_null_band.py <artefact.json> "
              "[--draws 4000] [--json out.json]")
        print("Nothing was read, so this says nothing about any object.")
        return 6
    path = positional[0] if positional else DEFAULT
    draws = opts["draws"]
    OUT_PATH = opts["json"]

    payload = {"target": os.path.abspath(path),
               "target_sha256": None,
               "draws": draws,
               "state": None,
               "deltas": {},
               "inside": [], "off": [], "gaps": []}

    print("=" * 78)
    print("76_E5p_null_band -- null band for within_t0_auc, from bin structure")
    print("  target: %s" % path)
    print("=" * 78)

    if not os.path.exists(path):
        print("\nABSENT: no file at that path. This is a statement about the")
        print("        filesystem, NOT about the experiment.")
        payload["state"] = "absent"
        return finish(payload, 3)
    try:
        with io.open(path, "rb") as fh:
            raw = fh.read()
        payload["target_sha256"] = hashlib.sha256(raw).hexdigest()
        r = json.loads(raw.decode("utf-8"))
    except Exception as exc:                                  # noqa: BLE001
        print("\nUNPARSEABLE (%s: %s) -- cannot derive a band. Do not report "
              "either 'at chance' or 'off chance'." % (type(exc).__name__, exc))
        payload["state"] = "unparseable"
        return finish(payload, 3)

    ctl = ((r.get("leakage_check") or {}).get("shuffled_label_control") or {})
    per = ctl.get("test_within_t0_auc_by_delta") or {}
    if not per:
        print("\nNO within-t0 block on the control -- nothing to derive from.")
        print("        This is a statement about the RECORD, not the science.")
        payload["state"] = "no_control_block"
        return finish(payload, 3)

    verdicts = {}
    print("\n%-6s %8s %6s %6s %10s %22s %10s" %
          ("delta", "n_bins", "skip", "SE", "99% band", "reading", "verdict"))
    for D in DELTAS:
        blk = per.get(D)
        rec = {"n_bins": None, "skipped": None, "se": None,
               "band": None, "mc_band": None, "reading": None, "inside": None}
        payload["deltas"][D] = rec
        if not isinstance(blk, dict) or not blk.get("per_bin"):
            print("%-6s   (no per_bin recorded -- cannot derive)" % D)
            verdicts[D] = None
            continue
        se, nbins, skipped = weighted_null_se(blk["per_bin"])
        # THE READING IS READ LAST, and only to locate it in the band.
        v = blk.get("weighted")
        rec["reading"] = v if isinstance(v, (int, float)) else None
        if se is None:
            print("%-6s %8s %6d   (no usable bins -- cannot derive)" % (D, "-", skipped))
            rec["n_bins"] = nbins
            rec["skipped"] = skipped
            verdicts[D] = None
            continue
        lo, hi = 0.5 - Z99 * se, 0.5 + Z99 * se
        mc = mc_band(blk["per_bin"], draws)
        inside = v is not None and lo <= v <= hi
        verdicts[D] = inside
        rec.update({"n_bins": nbins, "skipped": skipped, "se": se,
                    "band": [lo, hi], "mc_band": list(mc) if mc else None,
                    "inside": inside, "weighted": rec["reading"]})
        print("%-6s %8d %6d %6.4f %9.4f..%.4f %10s %10s" %
              (D, nbins, skipped, se, lo, hi,
               ("%.5f" % v) if isinstance(v, (int, float)) else repr(v),
               "INSIDE" if inside else "OUTSIDE"))
        if mc:
            print("        monte-carlo 99%% band (draws=%d): %.4f .. %.4f" %
                  (draws, mc[0], mc[1]))
        print("        hard-coded band that was used: 0.4500 .. 0.5500")

    real = [D for D in DELTAS if verdicts.get(D) is not None]
    gaps = [D for D in DELTAS if verdicts.get(D) is None]
    payload["gaps"] = gaps
    print("\n" + "=" * 78)
    if not real:
        print("CANNOT DERIVE for any delta. Report neither verdict.")
        payload["state"] = "cannot_derive"
        return finish(payload, 3)
    inside = [D for D in real if verdicts[D]]
    off = [D for D in real if not verdicts[D]]
    payload["inside"] = inside
    payload["off"] = off
    payload["state"] = "assessed"
    if inside:
        print("INSIDE the derived null band at %d delta(s): %s"
              % (len(inside), ", ".join(inside)))
        print("The control is consistent with chance THERE. If the hard-coded 0.05")
        print("also passed, that band was adequate here; this does not")
        print("retroactively justify it as a constant.")
    if gaps:
        print("NOT ASSESSED at %d delta(s): %s -- no per_bin to derive from."
              % (len(gaps), ", ".join(gaps)))
        print("This is a statement about the RECORD, not about the science.")
    if off:
        print("OUTSIDE the derived null band at: %s" % ", ".join(off))
        print("This is NOT a band specification problem. Under the label-only null")
        print("model the reading is too far from 0.5 to be sampling noise, so the")
        print("control is genuinely off-chance. Report it as a finding; do not")
        print("explain it away by widening any band.")
    # A delta that was never assessed must not be reported as if it had been.
    # Returning 0 while a delta is missing would tell a code-only consumer "the
    # control is at chance" about a delta this tool never looked at.
    if off and gaps:
        print("\nBOTH states: an off-chance finding AND unassessed delta(s). "
              "Neither is subordinate. Read the lines.")
        payload["verdict"] = "BOTH"
        return finish(payload, 5)
    if off:
        payload["verdict"] = "OUTSIDE"
        return finish(payload, 2)
    if gaps:
        print("\nINCOMPLETE: the control is inside where it could be assessed, "
              "but %d delta(s) were not assessed at all." % len(gaps))
        payload["verdict"] = "INCOMPLETE"
        return finish(payload, 4)
    payload["verdict"] = "INSIDE"
    return finish(payload, 0)


if __name__ == "__main__":
    sys.exit(main())
