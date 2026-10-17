#!/usr/bin/env bash
# pod_status.sh -- one-shot health and progress snapshot.
#
# Two lessons are baked into this version, both from readings that were wrong in
# a confident, well-formed way:
#
# 1. The package check must run in the `cis` interpreter. An earlier version
#    printed a tail of setup_env.log, whose last line was `BAD : lifelines
#    (ModuleNotFoundError); shap (ModuleNotFoundError)` -- a line written BEFORE
#    those packages were installed. It was read as current state for two runs.
#    A log line is a record of the past; only a live import answers the present.
# 2. The snapshot reports what the .py files can see, not just what the shell can.
#
# Single-line construction by design: this is pushed as a file and run, so the
# polling call is always `rsc.py script pod_status.sh` and never a multi-line
# inline command (a multi-line exec arrives with its newlines flattened).
set -u
R=/root/cis
PY=/usr/local/miniconda3/envs/cis/bin/python

echo "===== TIME ====="
date -Is

echo "===== PROCESSES ====="
pgrep -af 'setup_env|fetch_elliptic|fetch_data' | grep -v pod_status | head -8
echo "(none listed above = idle)"

echo "===== ENV: live check in the cis interpreter ====="
if [ -x "$PY" ]; then
  "$PY" - <<'PYEOF' 2>&1 | tail -25
import importlib
ok = bad = 0
for m in ("numpy","pandas","scipy","sklearn","statsmodels","networkx","pyarrow",
          "duckdb","matplotlib","seaborn","torch","torch_geometric","lifelines",
          "shap","transformers","datasets","peft","trl","bitsandbytes","accelerate",
          "python_louvain","sentencepiece","openpyxl"):
    try:
        mod = importlib.import_module(m)
        print("  OK  %-18s %s" % (m, getattr(mod, "__version__", "?")))
        ok += 1
    except Exception as e:
        print("  --  %-18s %s" % (m, type(e).__name__))
        bad += 1
print("LIVE_IMPORT ok=%d missing=%d" % (ok, bad))
PYEOF
else
  echo "  cis interpreter NOT PRESENT at $PY"
fi

echo "===== CUDA ====="
"$PY" -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())" 2>&1 | tail -2

echo "===== LOG TAIL (historical, not current state) ====="
echo "-- setup_env.sh last line (a record of 2026-09-23T16:34, may be stale):"
tail -1 "$R/logs/setup_env.log" 2>/dev/null || echo "   (no setup log)"

echo "===== ELLIPTIC++ LFS ====="
echo "pointer_remaining=$(grep -rl 'git-lfs.github.com/spec/v1' "$R/data/EllipticPlusPlus-main" --include='*.csv' --include='*.txt' 2>/dev/null | wc -l)"
du -sh "$R/data/EllipticPlusPlus-main" 2>/dev/null
echo "-- cache:"; ls -l "$R/data/lfs_cache" 2>/dev/null | tail -4
echo "-- fetcher log tail:"; tail -4 "$R/logs/lfs_resume.log" 2>/dev/null || echo "   (no fetcher log)"

echo "===== WORK / RESULTS ====="
ls -1 "$R/work" 2>/dev/null | head -20
echo "-- results:"; ls -1 "$R/results" 2>/dev/null | head -20

echo "===== DISK ====="
df -h /root | tail -1

echo "===== STATUS_DONE ====="
