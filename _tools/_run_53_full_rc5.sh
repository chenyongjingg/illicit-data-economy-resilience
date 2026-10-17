#!/bin/bash
# rc5 -- relaunch E5p after the 2026-09-24T04:55Z pod restart killed rc4.
#
# WHERE rc4 DIED. rc4 started 04:23:37Z and its log's last line is
# `[53 1653.5s] tgn ep3`; the pod reports `up 0 min` at 04:56Z. So rc4 was killed
# by an EXTERNAL restart at ~70% of a ~2400s run, with no artefact written. It is
# recorded as such rather than left as "no artefact", because a later reader who
# sees only an empty 53_E5p_result.json will otherwise re-litigate a run that was
# killed from outside its own control.
#
# WHY A NEW RUN ID AND NOT "rc4 CONTINUED". The restart re-attached THE SAME
# DEGRADED CARD -- gpu_preflight.py -v on the rebooted pod returns all three C-27
# repair markers verbatim ("GPU requires reset", "Channel Repair Pending", "TPC
# Repair Pending"), cuInit rc=100, torch.cuda.is_available() == False. So rc5's
# device is CPU, and a CPU population and a GPU population must never share a
# result file. rc5 is therefore a new run id.
#
# ON RE-FREEZING ANYTHING. The device did not change (rc4 was CPU too -- the card
# was already unusable), so no value expectation is re-frozen, and none may be:
# rc4's partial log already printed sage ep2 0.7878..., so any "expected" AUC
# written now would be post-hoc by construction. What IS new is that the device
# is now RECORDED (the header's device block) -- in the landed run and in rc4 the
# strings "cuda" / "cpu" / "thread" do not appear at all, so a CPU run and a GPU
# run were indistinguishable. That gap is closed here, not papered over.
#
# THE RC3 LESSON, APPLIED. rc3's launcher DESCRIBED a truncation in a comment and
# never wrote the statement, so rc3 appended to rc2's 89 lines. Here the
# truncation is asserted on CONTENT: the writer's own progress prefix `[53 ` must
# be absent. A line count would assert the wrong quantity, because the header's
# length now varies with the device block.
set -u

LOG=/root/cis/logs/53_full.log
KEEP=/root/cis/logs/53_full_rc4_partial_reboot_20260924.log
WRITER=/root/cis/scripts/53_E5p_temporal_gnn.py
WANT_SHA=077cb37906477179f20a0ec6d7a6dbc230c1f294f2f078b195828bc2452a7f8f
PY=/usr/local/miniconda3/envs/cis/bin/python

# 1. the writer must be the FROZEN one: rc5 has to be comparable with rc4 and
#    with the landed population, and a silent writer swap would make it neither.
got=$(sha256sum "$WRITER" | cut -d' ' -f1)
if [ "$got" != "$WANT_SHA" ]; then
    echo "WRITER SHA MISMATCH: want=$WANT_SHA got=$got" >&2
    exit 5
fi

# 2. do not clobber an existing preserve.
if [ -e "$KEEP" ]; then
    echo "preserve target EXISTS: $KEEP -- refusing to overwrite it" >&2
    exit 6
fi

# 3. the live log must BE rc4's, and rc4 must NOT have finished.
if [ ! -s "$LOG" ]; then
    echo "rc4 live log missing or empty: $LOG" >&2
    exit 3
fi
if ! grep -q "writer sha256: $WANT_SHA" "$LOG"; then
    echo "live log header does not name the frozen writer -- not rc4's log" >&2
    exit 7
fi
if grep -q "RSC_EXIT=" "$LOG"; then
    echo "live log carries a terminal marker: rc4 FINISHED -- refusing to rerun" >&2
    exit 8
fi
rc4_bytes=$(stat -c %s "$LOG")
rc4_lines=$(wc -l < "$LOG")
mv "$LOG" "$KEEP" || exit 9
echo "rc4 partial log preserved: $KEEP (${rc4_bytes} B, ${rc4_lines} lines)"

# 4. truncate, then ASSERT the truncation took effect (see rc3 note above).
: > "$LOG"
{
    echo "=== rc5 launch $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
    echo "writer sha256: $WANT_SHA"
    echo "cmdline: --epochs 6 --mlp-epochs 20 --eval-every 2"
    echo "cwd: /root"
    echo "reason: rc4 killed by pod restart 2026-09-24T04:55Z at t=1653.5s (tgn ep3)"
    echo "rc4 partial log: $KEEP (${rc4_bytes} B, ${rc4_lines} lines)"
} >> "$LOG"
PYTHONIOENCODING=utf-8 "$PY" /root/cis/_tools/_device_block.py >> "$LOG" 2>&1
echo "=== end header ===" >> "$LOG"

if grep -q '^\[53 ' "$LOG"; then
    echo "TRUNCATION DID NOT TAKE: old writer output is still present" >&2
    exit 4
fi
if [ "$(tail -1 "$LOG")" != "=== end header ===" ]; then
    echo "header did not close cleanly" >&2
    exit 4
fi
if ! grep -q '^device.device=' "$LOG"; then
    echo "device block missing -- the run's device would be unrecorded" >&2
    exit 4
fi
echo "header asserted: $(wc -l < "$LOG") lines, $(grep -m1 '^device.device=' "$LOG")"

# 5. run. CWD is /root, matching rc4: the output paths in the writer are absolute
#    (OUT_JSON = /root/cis/results/...), but the CWD is still pinned so that a
#    future relative path cannot silently differ between runs.
cd /root || exit 9
PYTHONIOENCODING=utf-8 "$PY" -u "$WRITER" \
    --epochs 6 --mlp-epochs 20 --eval-every 2 >> "$LOG" 2>&1
rc=$?
echo "RSC_EXIT=$rc" >> "$LOG"
echo "launcher: end $(date -u +%FT%TZ) rc=$rc"
exit $rc
