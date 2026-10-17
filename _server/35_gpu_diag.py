#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""35_gpu_diag.py -- why can torch not see the 4090?

C-27 recorded the GPU as unusable and left E5-E8 blocked. The state is:
  card present (RTX 4090, 24564 MiB), driver 610.57.04 (CUDA UMD 13.3),
  libcuda.so.1 dlopen()s OK, torch 2.5.1+cu124, yet
  torch.cuda.is_available() is False.

A False from is_available() is not a diagnosis: it swallows the underlying
error. This prints the actual exception from a real CUDA initialisation, plus
the device-node and driver-side state, so the cause is named rather than
guessed.
"""
import ctypes
import os
import subprocess
import sys

print("=" * 70)
print("GPU diagnosis")
print("=" * 70)

print("\n1. device nodes")
for pat in ("/dev/nvidia0", "/dev/nvidiactl", "/dev/nvidia-uvm",
            "/dev/nvidia-uvm-tools"):
    print("   %-24s %s" % (pat, "present" if os.path.exists(pat) else "MISSING"))
try:
    print("   /dev/nvidia* -> %s" % sorted(
        n for n in os.listdir("/dev") if n.startswith("nvidia")))
except Exception as e:  # noqa: BLE001
    print("   listing /dev failed: %r" % e)

print("\n2. driver / runtime versions")
for cmd in (["nvidia-smi", "--query-gpu=driver_version,name,memory.total",
             "--format=csv,noheader"],
            ["nvcc", "--version"]):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        print("   $ %s\n     %s" % (" ".join(cmd),
                                    (r.stdout or r.stderr).strip()
                                    .replace("\n", "\n     ")))
    except Exception as e:  # noqa: BLE001
        print("   $ %s -> %r" % (" ".join(cmd), e))

print("\n3. libcuda function calls (does the driver answer?)")
try:
    cuda = ctypes.CDLL("libcuda.so.1")
    cuda.cuInit.restype = ctypes.c_int
    cuda.cuInit.argtypes = [ctypes.c_uint]
    rc = cuda.cuInit(0)
    print("   cuInit(0) -> %d %s" % (rc, "(0 = CUDA_SUCCESS)" if rc == 0 else ""))
    n = ctypes.c_int(-1)
    cuda.cuDeviceGetCount.restype = ctypes.c_int
    cuda.cuDeviceGetCount.argtypes = [ctypes.POINTER(ctypes.c_int)]
    rc2 = cuda.cuDeviceGetCount(ctypes.byref(n))
    print("   cuDeviceGetCount -> rc=%d count=%d" % (rc2, n.value))
    if rc2 == 0 and n.value > 0:
        dev = ctypes.c_int()
        cuda.cuDeviceGet.restype = ctypes.c_int
        cuda.cuDeviceGet.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
        rc3 = cuda.cuDeviceGet(ctypes.byref(dev), 0)
        print("   cuDeviceGet(0) -> rc=%d handle=%d" % (rc3, dev.value))
        name = ctypes.create_string_buffer(256)
        cuda.cuDeviceGetName.restype = ctypes.c_int
        cuda.cuDeviceGetName.argtypes = [ctypes.c_char_p, ctypes.c_int,
                                         ctypes.c_int]
        rc4 = cuda.cuDeviceGetName(name, 256, dev.value)
        print("   cuDeviceGetName -> rc=%d name=%s" % (rc4, name.value.decode()))
except Exception as e:  # noqa: BLE001
    print("   FAILED: %r" % e)

print("\n4. torch, WITH the real exception")
try:
    import torch
    print("   torch          : %s" % torch.__version__)
    print("   torch.version.cuda: %s" % torch.version.cuda)
    print("   _C._cuda_getDeviceCount() -> %s"
          % (torch._C._cuda_getDeviceCount(),))
except Exception as e:  # noqa: BLE001
    print("   _cuda_getDeviceCount raised: %s: %s"
          % (type(e).__name__, e))
try:
    import torch
    torch.cuda.init()
    print("   torch.cuda.init() OK; device_count=%d"
          % torch.cuda.device_count())
except Exception as e:  # noqa: BLE001
    print("   torch.cuda.init() RAISED: %s: %s" % (type(e).__name__, e))

print("\n5. torch's bundled CUDA libs")
try:
    import torch, glob, os as _os
    d = _os.path.join(_os.path.dirname(torch.__file__), "lib")
    for f in sorted(glob.glob(d + "/*.so*"))[:40]:
        print("   %s" % _os.path.basename(f))
except Exception as e:  # noqa: BLE001
    print("   %r" % e)

print("\n6. environment")
for k in ("CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES",
          "NVIDIA_DRIVER_CAPABILITIES", "LD_LIBRARY_PATH"):
    print("   %-26s %s" % (k, os.environ.get(k, "<unset>")))

print("\n7. build metadata of the installed torch (is it a CUDA build?)")
try:
    import torch
    print("   torch.version.cuda = %r (None means a CPU-only wheel)"
          % (torch.version.cuda,))
    print("   torch.backends.cuda.is_built() = %s"
          % (torch.backends.cuda.is_built(),))
except Exception as e:  # noqa: BLE001
    print("   %r" % e)

print("\nDONE")
sys.exit(0)
