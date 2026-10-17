#!/bin/sh
# Relaunch E5p after the C-174 fix: `wtauc` selects its score column, and
# `within_t0_auc` refuses non-1-D input at its boundary.
#
# WHAT CHANGED VS THE RUN THAT DIED (rc2, 2,636 s in, no artefact written):
#   :1321  within_t0_auc(t0v[m], Y[m, k], scores[m])  ->  scores[m, k]
#   plus a 1-D guard at the top of within_t0_auc.
# Same arms, same budget, same command line, so the only difference between the
# runs is those two edits -- both of which are behaviour-preserving wherever the
# old code worked (verified: pre-fix and post-fix return an identical value when
# handed a column; see _tools/_verify_wtauc_fix.py cases C/D/E).
#
# LOG HANDLING -- WHY THIS IS NOT THE OLD LAUNCHER COPIED.
# The previous launcher copied $LOG to a FIXED name and guarded the copy on that
# name being ABSENT. That name already existed (the earlier rc=1 run), so the
# guard was false and `: > "$LOG"` would have DESTROYED the rc2 crash log -- the
# only record of the traceback this fix exists to answer. So: assert the rc2 log
# is already preserved before truncating anything, and refuse otherwise.
LOG=/root/cis/logs/53_full.log
KEEP=/root/cis/logs/53_full_rc2_wtauc_crash_20260924.log

if [ ! -f "$KEEP" ]; then
    echo "rc2 crash log ABSENT ($KEEP) -- refusing to truncate the live log" >&2
    exit 3
fi
echo "rc2 crash log preserved: $KEEP"

# Record WHICH OBJECT produced this run, in the run's own log. The failure mode
# this project keeps meeting is a reading quoted without its object's identity,
# and a log that does not name its writer cannot be matched to one.
{
    echo "=== rc3 launch $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
    echo "writer sha256: $(sha256sum /root/cis/scripts/53_E5p_temporal_gnn.py | cut -d' ' -f1)"
    echo "cmdline: --epochs 6 --mlp-epochs 20 --eval-every 2"
    echo "=== end header ==="
} >> "$LOG"

cd /root
PYTHONIOENCODING=utf-8 /usr/local/miniconda3/envs/cis/bin/python -u \
    /root/cis/scripts/53_E5p_temporal_gnn.py \
    --epochs 6 --mlp-epochs 20 --eval-every 2 >> "$LOG" 2>&1

echo "RSC_EXIT=$?" >> "$LOG"
