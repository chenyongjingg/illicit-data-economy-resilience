#!/bin/sh
# Relaunch E5p after the C-174 fix: `wtauc` selects its score column, and
# `within_t0_auc` refuses non-1-D input at its boundary.
#
# WHAT CHANGED VS THE RUN THAT DIED (rc2, 2,636 s in, no artefact written):
#   :1336  within_t0_auc(t0v[m], Y[m, k], scores[m])  ->  scores[m, k]
#   plus a 1-D guard at the top of within_t0_auc.
# Same arms, same budget, same command line, so the only difference between the
# runs is those two edits -- both behaviour-preserving wherever the old code
# worked (pre-fix and post-fix return an identical value when handed a column;
# _tools/_verify_wtauc_fix.py cases C/D/E).
#
# WHY rc3 WAS ABORTED ONE MINUTE IN (and why this file is not rc3).
# rc3's launcher PRESERVED the rc2 crash log correctly but then never truncated
# the live log -- the truncation was described in a comment and not written as a
# statement. So rc3 APPENDED to rc2's 89 lines, and the live log was
#     89 (rc2, including its own "RSC_EXIT=1" line) + 4 (header) + 5 (rc3)
# = 98 lines exactly. Two consequences: rc2's traceback sat in the middle of the
# live log, and any watcher counting "RSC_EXIT=" occurrences would have read
# TERMINAL on tick one, from the previous run's line -- a false "run ended" that
# names the wrong run. rc3 was aborted 1 minute in with no artefact, so the cost
# of restarting was one minute and the cost of not restarting was an ambiguous
# log. A comment that claims behaviour the code does not implement is the same
# defect class as the writer's hardcoded `selection_was_blinded_to_true_labels`.
#
# SO THIS VERSION ASSERTS THE TRUNCATION TOOK EFFECT rather than asserting it
# happened. `: > "$LOG"` then a line-count check on the header alone: if the file
# is not exactly the header, exit 4 without starting python.
LOG=/root/cis/logs/53_full.log
KEEP=/root/cis/logs/53_full_rc2_wtauc_crash_20260924.log

if [ ! -f "$KEEP" ]; then
    echo "rc2 crash log ABSENT ($KEEP) -- refusing to truncate anything" >&2
    exit 3
fi
echo "rc2 crash log preserved: $KEEP"

: > "$LOG"

{
    echo "=== rc4 launch $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
    echo "writer sha256: $(sha256sum /root/cis/scripts/53_E5p_temporal_gnn.py | cut -d' ' -f1)"
    echo "cmdline: --epochs 6 --mlp-epochs 20 --eval-every 2"
    echo "=== end header ==="
} >> "$LOG"

n=$(wc -l < "$LOG")
if [ "$n" -ne 4 ]; then
    echo "TRUNCATION DID NOT TAKE: log has $n lines, expected 4" >&2
    exit 4
fi
echo "log truncated and header written: $n lines, first=$(head -1 "$LOG")"

cd /root
PYTHONIOENCODING=utf-8 /usr/local/miniconda3/envs/cis/bin/python -u \
    /root/cis/scripts/53_E5p_temporal_gnn.py \
    --epochs 6 --mlp-epochs 20 --eval-every 2 >> "$LOG" 2>&1

echo "RSC_EXIT=$?" >> "$LOG"
