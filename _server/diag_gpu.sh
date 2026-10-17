#!/usr/bin/env bash
# diag_gpu.sh -- why does torch report cuda False when nvidia-smi sees the GPU?
#
# nvidia-smi reporting a healthy RTX 4090 proves the *driver* and the device
# node are present. It does not prove that a CUDA runtime loaded from a conda
# env can see them. Those are different questions, and the gap between them is
# where this is failing, so each is tested separately below.
set -u
PY=/usr/local/miniconda3/envs/cis/bin/python

echo "===== 1. driver view ====="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>&1 | head -4
echo "nvml driver: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>&1 | head -1)"

echo "===== 2. device nodes ====="
ls -l /dev/nvidia* 2>&1 | head -10
echo "--- cuda libs on the system ---"
ls /usr/lib/x86_64-linux-gnu/libcuda* 2>&1 | head -5
ldconfig -p 2>/dev/null | grep -E "libcuda\.so|libnvidia-ml" | head -5

echo "===== 3. environment variables that gate visibility ====="
echo "CUDA_VISIBLE_DEVICES='${CUDA_VISIBLE_DEVICES-<unset>}'"
echo "NVIDIA_VISIBLE_DEVICES='${NVIDIA_VISIBLE_DEVICES-<unset>}'"
echo "LD_LIBRARY_PATH='${LD_LIBRARY_PATH-<unset>}'"

echo "===== 4. what torch itself says ====="
$PY - <<'PY' 2>&1 | head -25
import ctypes, os, sys
print("torch", __import__("torch").__version__)
try:
    ctypes.CDLL("libcuda.so.1")
    print("libcuda.so.1 loadable: True")
except OSError as e:
    print("libcuda.so.1 loadable: False ->", e)
import torch
print("torch.version.cuda =", torch.version.cuda)
print("is_available        =", torch.cuda.is_available())
print("device_count        =", torch.cuda.device_count())
try:
    print("_cuda_getDeviceCount=", torch._C._cuda_getDeviceCount())
except Exception as e:
    print("_cuda_getDeviceCount raised:", type(e).__name__, e)
try:
    print("cudart version      =", torch.cuda.cudart().cudaRuntimeGetVersion())
except Exception as e:
    print("cudart probe raised :", type(e).__name__, e)
print("torch lib dir       =", os.path.dirname(torch.__file__))
PY

echo "===== 5. does the bundled nvidia runtime actually load? ====="
$PY - <<'PY' 2>&1 | head -20
import glob, os, ctypes, sys
base = "/usr/local/miniconda3/envs/cis/lib/python3.11/site-packages/nvidia"
print("nvidia/ subdirs:", sorted(os.path.basename(p) for p in glob.glob(base + "/*")))
for name in ("cuda_runtime", "cudnn", "cublas"):
    libs = glob.glob(os.path.join(base, name, "lib", "*.so*"))
    print("%-14s %d libs" % (name, len(libs)), [os.path.basename(x) for x in libs[:3]])
cudart = glob.glob(base + "/cuda_runtime/lib/libcudart.so*")
if cudart:
    try:
        ctypes.CDLL(cudart[0])
        print("libcudart loadable: True")
    except OSError as e:
        print("libcudart loadable: False ->", e)
PY

echo "===== 6. torch's own runtime error, with the CUDA driver hint ====="
CUDA_LAUNCH_BLOCKING=1 $PY -c "
import torch
try:
    torch.zeros(4, device='cuda')
    print('cuda tensor ok')
except Exception as e:
    print(type(e).__name__, ':', str(e)[:600])
" 2>&1 | head -20

echo "===== 7. missing python packages ====="
$PY -c "
import importlib
for m in ('lifelines','shap','torch_geometric','transformers','peft','bitsandbytes','accelerate','datasets'):
    try:
        mod = importlib.import_module(m); print('  OK  %-16s %s' % (m, getattr(mod,'__version__','?')))
    except Exception as e:
        print('  --  %-16s %s' % (m, type(e).__name__))
" 2>&1 | head -12

echo "===== DIAG_GPU_DONE ====="
