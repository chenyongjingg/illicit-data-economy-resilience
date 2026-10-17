# -*- coding: utf-8 -*-
"""Append a review note to report 16. Append-only: the body is not rewritten."""
import io
import os

PATH = r"D:\CIS\pipeline_reports\16_E5p_temporal_gnn.md"

NOTE = u"""
---

## 9. Review note added after coordinator review (2026-09-24) — the header
## overstates, and two of this report's own decompositions disagree

Everything in the body stands. Two things should be read together with it.

**(a) The header's inference rests on the pooled column.** "Most of the arms'
apparent skill is not attributable to label-driven learning" is drawn from
control-pooled vs arm-pooled. §5 is explicit that those arms' pooled numbers
contain a large entry-timing component and that the control has **no** within-t0
reading. So the header's conclusion is licensed for the *pooled* metric and for
nothing else — and the pre-registered criterion it invokes
(`shuffled_control_at_chance`) is itself evaluated on `test_auc_by_delta`, the
pooled column, by the writer that produced this artefact.

The pooled column is the one that cannot separate the two hypotheses. Measured
here: across the 44 t0 bins at Δ=5 the positive rate spans 0.00152 → 0.18824, a
**124×** range. A scorer that reports only *which bin it is in* therefore clears
0.5 on the pooled metric with no label information whatever. Because a
whole-set label permutation preserves each bin's positive rate by the law of
large numbers, a model trained on permuted labels can learn exactly that and
score 0.81–0.84 pooled. On that reading the control's pooled 0.81 is the
**expected consequence of the t0 channel**, not evidence of leakage — which is
precisely why the fixed writer moves `shuffled_control_at_chance` onto the
within-t0 column. (Mechanism stated as a prediction; the run below tests it.)

**(b) §5 and the header decompose the same number two different ways and do not
reconcile.** §5 reports the calendar share of the excess as 23.6–36.6%, which
leaves 63–76% *label-driven*. The header reports that a no-label control matches
or beats the arms pooled, which leaves ~0%. Both cannot be read as stated. The
difference is that §5's share is computed against the arms' **within-t0** value,
while the control's 0.81 is on the **pooled** scale — the two decompositions use
different baselines. This report does not resolve which is the meaningful split,
and the missing measurement is again the thing that would.

**Neither reading changes the negative arm-vs-arm result of §5**, which is on the
within-t0 metric where all three arms share the same selection caveat.

**Remedy already running.** The coordinator relaunched E5p on 2026-09-24T03:34:54Z
(pid 36327) with the **fixed writer** (`1ebf15e85fe73026`, pod and local
byte-identical), which scores the control through `eval_block` and gives it a
`within_t0_auc` — the minimal change §5 names. If the control's within-t0 lands
near 0.5 while the arms sit at ~0.71–0.77, the header's conclusion is falsified;
if it lands near 0.7, it is confirmed. That is a decidable reading, not another
guess. Ledger: **C-160** in `pipeline_reports/progress.md`.
"""

raw = io.open(PATH, "rb").read()
assert raw.count(b"\r\n") == 0, "report is CRLF; refusing to change its endings"
before = len(raw)
with io.open(PATH, "a", encoding="utf-8", newline="\n") as fh:
    fh.write(NOTE)
after = os.path.getsize(PATH)
assert io.open(PATH, "rb").read()[:before] == raw, "not append-only"
print("report %d -> %d bytes (+%d), existing bytes untouched" % (before, after, after - before))
