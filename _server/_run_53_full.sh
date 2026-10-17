#!/bin/sh
# Relaunch E5p after the C-138 fix: `TxAddr_edgelist.csv` joins ACT, not TXD.
#
# What changed vs the run that exited rc=1: ONE line (the directory constant)
# plus its comment. Same arms, same budget, same command line, so the only
# difference between the two runs is the fixed path.
#
# The previous run's log is preserved rather than overwritten -- it is the
# record of a failed run and carries the two control trajectories that were
# produced before the crash.

LOG=/root/cis/logs/53_full.log
KEEP=/root/cis/logs/53_full_rc1_20260924.log

if [ -f "$LOG" ] && [ ! -f "$KEEP" ]; then
    cp -p "$LOG" "$KEEP"
    echo "preserved previous log -> $KEEP"
fi

: > "$LOG"

cd /root
PYTHONIOENCODING=utf-8 /usr/local/miniconda3/envs/cis/bin/python -u \
    /root/cis/scripts/53_E5p_temporal_gnn.py \
    --epochs 6 --mlp-epochs 20 --eval-every 2 >> "$LOG" 2>&1

echo "RSC_EXIT=$?" >> "$LOG"
