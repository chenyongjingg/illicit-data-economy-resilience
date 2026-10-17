#!/usr/bin/env bash
# gpu_recheck.sh -- is the ERR!/CUDA_ERROR_NO_DEVICE state persistent or transient?
#
# Evidence so far:
#   * kernel module 610.57.04 and userspace libcuda.so.610.57.04 MATCH (so the
#     usual driver/library mismatch is ruled out, not assumed);
#   * cuDriverGetVersion = 13030 (driver speaks CUDA 13.3);
#   * cuInit(0) returns 100 = CUDA_ERROR_NO_DEVICE.
# nvidia-smi flags the row "ERR!" while still reading the device through NVML --
# NVML and the CUDA driver API are different code paths, so NVML succeeding while
# cuInit fails is consistent and is not a contradiction.
#
# This script does NOT reset anything. A GPU reset on a shared host would disrupt
# other tenants, so it is treated as a separate, deliberate decision.
set -u
PY=/usr/local/miniconda3/envs/cis/bin/python

echo "===== full /proc/driver/nvidia/gpus enumeration ====="
for d in /proc/driver/nvidia/gpus/*/; do
  echo "--- $d"
  cat "$d/information" 2>/dev/null | sed 's/^/    /'
done

echo "===== /dev nodes vs driver minors ====="
ls -l /dev/nvidia0 /dev/nvidia1 /dev/nvidiactl 2>&1
echo "driver-reported minors:"
grep -h "Device Minor" /proc/driver/nvidia/gpus/*/information 2>/dev/null

echo "===== sysfs ====="
ls /sys/class/nvidia* 2>/dev/null | head
cat /proc/driver/nvidia/params 2>/dev/null | grep -iE "devicefile|minor" | head

echo "===== cuInit retried 4x over 45s (transient?) ====="
$PY - <<'PY'
import ctypes, time
lib = ctypes.CDLL("libcuda.so.1")
for i in range(4):
    rc = lib.cuInit(0)
    n = ctypes.c_int()
    rc2 = lib.cuDeviceGetCount(ctypes.byref(n))
    print("  try %d: cuInit rc=%d  cuDeviceGetCount rc=%d count=%d" % (i + 1, rc, rc2, n.value))
    if rc == 0 and n.value:
        print("  GPU became available")
        break
    if i < 3:
        time.sleep(15)
PY

echo "===== cross-check: does the image's own python see it? ====="
for p in /usr/local/miniconda3/bin/python3 /usr/bin/python3; do
  if [ -x "$p" ]; then
    echo "--- $p"
    "$p" -c "import torch;print('  torch',torch.__version__,'cuda',torch.cuda.is_available())" 2>&1 | head -2
  fi
done

echo "===== nvidia-smi error counters and Xid surface ====="
nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,ecc.errors.uncorrected.volatile.total --format=csv 2>&1 | head -4
nvidia-smi -q 2>&1 | grep -iE "Xid|error|ERR!|Retired|Remapped|Pending" | head -12

echo "===== can we open the device node directly? ====="
$PY -c "
import os
for n in ('/dev/nvidia0','/dev/nvidiactl','/dev/nvidia-uvm'):
    try:
        fd=os.open(n, os.O_RDWR)
        os.close(fd); print('  open ok  ', n)
    except OSError as e:
        print('  open FAIL', n, e)
"

echo "===== GPU_RECHECK_DONE ====="
