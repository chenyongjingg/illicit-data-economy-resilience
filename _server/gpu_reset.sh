#!/usr/bin/env bash
# gpu_reset.sh -- attempt the reset the driver is explicitly asking for.
#
# Justification, stated before the act because this touches shared hardware:
#   * the device is ALREADY non-functional -- cuInit returns CUDA_ERROR_NO_DEVICE
#     persistently, and nvidia-smi marks the row "ERR!";
#   * nvidia-smi -q reports "GPU requires reset" under Remapped Rows, Channel
#     Repair Pending, and TPC Repair Pending -- i.e. the driver itself is asking;
#   * nothing is running on it: 1 MiB used, no compute apps listed;
#   * the pod is a single-GPU allocation, and a reset to a device that already
#     fails CUDA enumeration cannot destroy a working neighbour's work.
# If the reset succeeds, E5-E8 (the GPU layer) become runnable. If it fails, the
# GPU layer is blocked and everything CPU-side proceeds regardless.
#
# Bounded: nvidia-smi -r can hang on a wedged device, so it runs under timeout.
set -u
echo "===== before ====="
$HOME/../usr/bin/true 2>/dev/null
nvidia-smi --query-gpu=index,name,memory.used --format=csv,noheader 2>&1 | head -2
/usr/local/miniconda3/envs/cis/bin/python -c "
import ctypes
lib = ctypes.CDLL('libcuda.so.1')
n = ctypes.c_int()
print('  cuInit rc=%d' % lib.cuInit(0))
lib.cuDeviceGetCount(ctypes.byref(n)); print('  count=%d' % n.value)
" 2>&1

echo "===== reset (bounded to 120s) ====="
timeout 120 nvidia-smi -r -i 0 2>&1 | head -20
rc=$?
echo "reset rc=$rc"

echo "===== settling 20s ====="
sleep 20

echo "===== after ====="
nvidia-smi --query-gpu=index,name,memory.used,temperature.gpu --format=csv,noheader 2>&1 | head -2
/usr/local/miniconda3/envs/cis/bin/python -c "
import ctypes, torch
lib = ctypes.CDLL('libcuda.so.1')
n = ctypes.c_int()
rc = lib.cuInit(0)
lib.cuDeviceGetCount(ctypes.byref(n))
print('  cuInit rc=%d  count=%d' % (rc, n.value))
print('  torch.cuda.is_available() =', torch.cuda.is_available())
if torch.cuda.is_available():
    a = torch.randn(1024, 1024, device='cuda'); print('  gpu matmul ok ->', float((a @ a).sum()))
" 2>&1 | head -10

echo "===== GPU_RESET_DONE ====="
