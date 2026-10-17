#!/bin/bash
# Relaunch E5p with the FIXED writer (1ebf15e85fe73026).
#
# Same command, same arms, same budget as the landed run; the only differences
# are the two C-159 fixes plus the within-t0 additions the fixed writer already
# carried. The point of the rerun is that the artefact should carry counters
# that are LIVE -- C-159 showed two of the landed run's columns could not
# disagree with `stored`, so their "0 mismatches" was vacuous, not clean.
#
# Log naming: 53_full.log is the canonical name, but we never silently truncate
# one. If it already exists it is preserved under a timestamped name first,
# because an overwritten log is an unrecoverable loss of the only record of a
# run that may have been cited.
cd /root/cis/scripts || exit 9
LOG=/root/cis/logs/53_full.log
PY=/usr/local/miniconda3/envs/cis/bin/python

if [ -e "$LOG" ]; then
    KEEP="/root/cis/logs/53_full.preserved_$(date -u +%Y%m%dT%H%M%SZ).log"
    mv "$LOG" "$KEEP" || exit 8
    echo "launcher: preserved existing log -> $KEEP"
fi

echo "launcher: writer sha256 $(sha256sum 53_E5p_temporal_gnn.py | cut -c1-16)"
echo "launcher: start $(date -u +%FT%TZ)"
"$PY" -u 53_E5p_temporal_gnn.py --epochs 6 --mlp-epochs 20 --eval-every 2 \
    > "$LOG" 2>&1
rc=$?
echo "launcher: end $(date -u +%FT%TZ)"
echo "RSC_EXIT=$rc" >> "$LOG"
exit $rc
