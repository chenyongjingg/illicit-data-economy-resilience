#!/usr/bin/env bash
# diag_gpu2.sh -- separate the kernel module from the userspace CUDA driver.
#
# "No CUDA GPUs are available" from a process that can load libcuda.so.1 and sees
# /dev/nvidia0 means the driver API refused to enumerate, not that the device is
# absent. The most common cause is that the userspace libcuda does not match the
# loaded kernel module. nvidia-smi cannot detect this because it goes through
# NVML, a different library -- so NVML succeeding is not evidence that CUDA works,
# which is exactly the trap the first diagnostic fell into.
set -u
PY=/usr/local/miniconda3/envs/cis/bin/python

echo "===== kernel module version (authoritative) ====="
cat /proc/driver/nvidia/version 2>&1
echo "--- loaded modules ---"
cat /proc/driver/nvidia/gpus/*/information 2>/dev/null | head -12

echo "===== userspace driver libraries ====="
for f in /usr/lib/x86_64-linux-gnu/libcuda.so.1 /lib/x86_64-linux-gnu/libcuda.so.1; do
  [ -e "$f" ] && printf '%s -> %s\n' "$f" "$(readlink -f "$f")"
done
ls -l /usr/lib/x86_64-linux-gnu/libcuda.so* 2>/dev/null
echo "--- NVML userspace ---"
ls -l /usr/lib/x86_64-linux-gnu/libnvidia-ml.so* 2>/dev/null

echo "===== nvidia-smi header (reports the CUDA version the driver supports) ====="
nvidia-smi 2>&1 | head -12

echo "===== kernel messages mentioning nvidia ====="
dmesg 2>/dev/null | grep -iE "nvidia|nvrm|cuda" | tail -15 || echo "(dmesg unavailable)"

echo "===== compute mode / persistence ====="
nvidia-smi --query-gpu=compute_mode,persistence_mode,ecc.mode.current,pstate --format=csv 2>&1 | head -4

echo "===== raw CUDA driver probe via ctypes (bypasses torch) ====="
$PY - <<'PY' 2>&1 | head -30
import ctypes, ctypes.util
lib = ctypes.CDLL("libcuda.so.1")
print("loaded:", lib._name)
v = ctypes.c_int()
r = lib.cuDriverGetVersion(ctypes.byref(v))
print("cuDriverGetVersion rc=%d value=%s" % (r, v.value if r == 0 else "n/a"))
n = ctypes.c_int()
r = lib.cuInit(0)
print("cuInit rc=%d" % r)
r = lib.cuDeviceGetCount(ctypes.byref(n))
print("cuDeviceGetCount rc=%d count=%d" % (r, n.value))
if r != 0:
    nm = ctypes.c_char_p()
    lib.cuGetErrorName(ctypes.c_int(r), ctypes.byref(nm))
    ds = ctypes.c_char_p()
    lib.cuGetErrorString(ctypes.c_int(r), ctypes.byref(ds))
    print("  error name:", nm.value, "| string:", ds.value)
if n.value > 0:
    dev = ctypes.c_int()
    print("cuDeviceGet rc=%d" % lib.cuDeviceGet(ctypes.byref(dev), 0))
    buf = ctypes.create_string_buffer(128)
    if lib.cuDeviceGetName(buf, 128, dev) == 0:
        print("device name:", buf.value.decode())
PY

echo "===== is another process holding the device exclusively? ====="
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>&1 | head -6
fuser -v /dev/nvidia0 2>&1 | head -6 || echo "(fuser unavailable)"

echo "===== DIAG_GPU2_DONE ====="
