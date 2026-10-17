#!/bin/bash
# CIS sprint -- build the `cis` env on the NEW pod.  Auto-generated, idempotent-ish.
#
# 纪律：
#  * torch 钉 **2.5.1**（旧 pod 同款）—— 镜像自带的 2.13.0+cu132 比它**新两个大版本**，
#    旧脚本在 2.13 上会**静默改变行为**（API 默认值变更）⇒ 可复现性优先。
#  * 全部走 TUNA 镜像（服务器内网/就近），**不占本地热点带宽**。
#  * 每步都 echo，末尾打印**实测**的 import 结果，不打印任何凭据。
set -u
LOG=/root/cis/logs/setup_cis_env.log
exec > >(tee -a "$LOG") 2>&1
echo "=== setup_cis_env start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

CONDA=/usr/local/miniconda3/bin/conda
PY=/usr/local/miniconda3/envs/cis/bin/python
TUNA=https://pypi.tuna.tsinghua.edu.cn/simple
export PIP_INDEX_URL="$TUNA"
export PIP_DEFAULT_TIMEOUT=120

echo "--- [1/5] conda create cis (python=3.10) ---"
if [ -x "$PY" ]; then
  echo "cis python already present: $($PY -V 2>&1)"
else
  "$CONDA" create -y -n cis python=3.10 || { echo "CONDA_CREATE_FAILED rc=$?"; exit 1; }
fi
"$PY" -V || { echo "NO_CIS_PYTHON"; exit 1; }

echo "--- [2/5] pip bootstrap ---"
"$PY" -m pip --version 2>/dev/null || "$PY" -m ensurepip --upgrade
"$PY" -m pip install -q --upgrade "pip<25" setuptools wheel || echo "PIP_UPGRADE_WARN"

echo "--- [3/5] torch 2.5.1 (cu124 build) ---"
"$PY" -c 'import torch,sys; sys.exit(0 if torch.__version__.startswith("2.5.1") else 1)' 2>/dev/null \
  && echo "torch 2.5.1 already installed" \
  || "$PY" -m pip install --no-cache-dir "torch==2.5.1" "torchvision==0.20.1" || { echo "TORCH_INSTALL_FAILED"; exit 1; }

echo "--- [4/5] scientific stack ---"
"$PY" -m pip install --no-cache-dir \
  "numpy==1.26.4" "scipy==1.13.1" "pandas==2.2.2" "scikit-learn==1.5.2" \
  "matplotlib==3.9.2" "pyarrow==17.0.0" "networkx==3.3" "statsmodels==0.14.3" \
  "lifelines==0.29.0" "seaborn==0.13.2" "tqdm==4.66.5" "pyyaml==6.0.2" \
  "requests==2.32.3" "beautifulsoup4==4.12.3" "lxml==5.3.0" "openpyxl==3.1.5" \
  "h5py==3.11.0" "joblib==1.4.2" || { echo "STACK_INSTALL_FAILED"; exit 1; }

echo "--- [4b/5] ML extras (graph / surrogate / stats) ---"
"$PY" -m pip install --no-cache-dir \
  "torch-geometric==2.6.1" "shap==0.46.0" "accelerate==1.0.1" \
  "datasets==3.0.1" "transformers==4.46.0" "peft==0.13.2" "bitsandbytes==0.44.1" \
  || echo "ML_EXTRAS_WARN (non-fatal; E5/E6/E7/E8 need these)"

echo "--- [5/5] VERIFY (measured, not assumed) ---"
"$PY" - <<'PYEOF'
import importlib.util as u, sys
mods = ("numpy","scipy","pandas","torch","sklearn","matplotlib","pyarrow","networkx",
        "lifelines","statsmodels","transformers","torch_geometric","shap","peft",
        "bitsandbytes","accelerate","datasets")
present = [m for m in mods if u.find_spec(m)]
absent  = [m for m in mods if not u.find_spec(m)]
print("python  :", sys.version.split()[0])
print("present :", present)
print("absent  :", absent)
import torch
print("torch   :", torch.__version__, "cuda_build", torch.version.cuda,
      "avail", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device  :", torch.cuda.get_device_name(0))
    a = torch.randn(512, 512, device="cuda"); b = torch.randn(512, 512, device="cuda")
    c = a @ b
    torch.cuda.synchronize()
    print("KERNEL_OK", bool(c.shape == (512, 512)))
else:
    print("KERNEL_OK False")
print("VERDICT:", "READY" if (not absent and torch.cuda.is_available()) else "PARTIAL")
PYEOF
echo "=== setup_cis_env done $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
