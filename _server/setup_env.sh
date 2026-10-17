#!/usr/bin/env bash
# setup_env.sh -- build the CIS experiment environment on the 4090 pod.
#
# Idempotent: safe to re-run; logs to /root/cis/logs/setup_env.log.
#
# Mirror choice (measured on this pod, 2026-09-24, each on a real 35 MB wheel
# with --no-cache-dir, so these are throughput and not latency on an index page):
#
#     pypi.tuna.tsinghua.edu.cn   13.53 MB/s   <- chosen
#     pypi.org (via pod proxy)     6.95 MB/s
#     mirrors.aliyun.com           0.34 MB/s   <- previous default, 40x slower
#     mirrors.ucloud.cn            n/a         (no scipy in its index)
#
# An earlier note in this project's ledger recorded "aliyun 8.2 MB/s vs tuna
# 0.5 MB/s" and picked aliyun on that basis. Both halves of that were wrong; the
# re-measurement above supersedes it (ledger C-23). The practical consequence was
# real: a hung 664.8 MB nvidia_cudnn_cu12 download.
#
# The pod's login shell exports a global http_proxy to mihomo. It is required for
# github.com (direct = 000) but is not the cause of the slow mirror.
#
# python 3.11 -- broadest wheel coverage for torch / PyG / bitsandbytes. The PyPI
# `torch` linux wheel is the CUDA build (cu124), correct for this 4090 + driver 610.
set -uo pipefail

ROOT=/root/cis
LOG=$ROOT/logs/setup_env.log
mkdir -p "$ROOT"/{logs,code,data,work,results,figures,reports}
exec > >(tee -a "$LOG") 2>&1

echo "=================== setup_env.sh $(date -Is) ==================="

export PATH=/usr/local/miniconda3/bin:$PATH
source /usr/local/miniconda3/bin/activate base

CONDA_ENV=cis
PYVER=3.11
TORCH_VER=2.5.1
MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple/
MIRROR_HOST=pypi.tuna.tsinghua.edu.cn

if ! conda env list | grep -qE "^${CONDA_ENV}\s"; then
  echo "--- creating conda env ${CONDA_ENV} (python ${PYVER}) ---"
  conda create -y -n "$CONDA_ENV" python="$PYVER" || { echo "FATAL: conda create failed"; exit 1; }
else
  echo "--- conda env ${CONDA_ENV} already exists ---"
fi

source /usr/local/miniconda3/bin/activate "$CONDA_ENV"
echo "python: $(which python) $(python -V 2>&1)"

pip config set global.index-url "$MIRROR" >/dev/null
pip config set global.trusted-host "$MIRROR_HOST" >/dev/null
pip config set global.timeout 120 >/dev/null
pip config set global.retries 5 >/dev/null
echo "pip index: $(pip config get global.index-url 2>/dev/null)  (pip $(pip -V | awk '{print $2}'))"

if python -c "import torch,sys; sys.exit(0 if torch.__version__.startswith('${TORCH_VER}') else 1)" 2>/dev/null; then
  echo "torch already present: $(python -c 'import torch;print(torch.__version__)')"
else
  echo "--- installing torch ${TORCH_VER} ---"
  pip install "torch==${TORCH_VER}" || { echo "FATAL: torch install failed"; exit 1; }
fi
python -c "import torch;print('torch',torch.__version__,'cuda_avail',torch.cuda.is_available(),'dev',torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-')"

echo "--- core scientific stack ---"
pip install "numpy<2.3" pandas scipy scikit-learn statsmodels networkx matplotlib seaborn \
  pyarrow duckdb tqdm requests pyyaml joblib psutil || echo "WARN: some core packages failed"

echo "--- survival / causal / graph extras ---"
pip install lifelines shap python-louvain || echo "WARN: extras partially failed"

echo "--- PyG ---"
pip install torch_geometric || echo "WARN: torch_geometric install failed"
# Optional compiled helpers; PyG falls back to native torch scatter ops without
# them, so their absence is not fatal.
pip install pyg-lib torch-scatter torch-sparse \
  -f "https://data.pyg.org/whl/torch-${TORCH_VER}+cu124.html" \
  || echo "NOTE: compiled PyG extensions unavailable; using pure-torch fallback"

echo "--- LLM stack (E8) ---"
pip install transformers accelerate peft bitsandbytes datasets sentencepiece \
  || echo "WARN: LLM stack partially failed"

echo "--- verification ---"
python - <<'PYEOF'
import importlib
mods = ["numpy","pandas","scipy","sklearn","statsmodels","networkx","matplotlib",
        "seaborn","pyarrow","duckdb","torch","torch_geometric","lifelines","shap",
        "transformers","peft","bitsandbytes","accelerate","datasets"]
ok, bad = [], []
for m in mods:
    try:
        mod = importlib.import_module(m)
        ok.append("%s=%s" % (m, getattr(mod, "__version__", "?")))
    except Exception as e:
        bad.append("%s (%s)" % (m, type(e).__name__))
print("OK  :", ", ".join(ok))
print("BAD :", "; ".join(bad) if bad else "none")
try:
    import torch
    print("CUDA:", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")
    if torch.cuda.is_available():
        x = torch.randn(512, 512, device="cuda")
        print("matmul on GPU ok:", float((x @ x).sum()))
except Exception as e:
    print("CUDA check failed:", e)
PYEOF

echo "=================== setup_env.sh DONE $(date -Is) ==================="
