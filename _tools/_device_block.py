# -*- coding: utf-8 -*-
"""Print the identity of the device a run is about to use, into the run's own log.

WHY THIS EXISTS (peer point 3, adopted). rc4's log has NO device vocabulary: the
string "cuda" does not appear in it, nor does a thread count, nor a hostname. So
a CPU run and a GPU run are indistinguishable in that record -- and the landed
run's device is therefore UNRECORDED and cannot be recovered after the fact. A
number whose device is unknown is not fully specified, because cuDNN/cuBLAS and
scatter-atomic reductions are not bit-deterministic and the licence band here is
+/-0.05: a device change can move a reading inside the band.

So the device is asserted BEFORE the run, by the launcher, into the run's log.

THE SENTINEL RULE (my own C-... register, the `cuDeviceGetCount` entry). When
`torch.cuda.is_available()` is False, `device_count()` is NOT a measurement of
"zero GPUs" -- the call is not reached, or is reached in a state where its answer
is undefined. Printing `0` there would be exactly the collision that register
warns about: `0` is the value a genuinely GPU-less host would also print, so two
different sources of `0` would hide a broken channel. So an unmeasured quantity
is printed as `-1` and is named as UNMEASURED on the same line.

Exit code is always 0 -- this is a recorder, not a gate. The gate is
gpu_preflight.py, which is a different script with a different verdict.
"""
import os
import platform
import socket
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print("--- device block ---")
print("device.hostname=%s" % socket.gethostname())
print("device.platform=%s" % platform.platform())
print("device.python=%s" % sys.version.split()[0])
print("device.cpu_count=%s" % (os.cpu_count(),))

try:
    import torch
except ImportError as exc:
    print("device.torch=ABSENT (%s)" % exc)
    print("device.device=unknown (no torch, so nothing was measured)")
    print("--- end device block ---")
    sys.exit(0)

print("device.torch_version=%s" % torch.__version__)
print("device.torch_cuda_built=%s" % torch.version.cuda)

avail = torch.cuda.is_available()
print("device.cuda_is_available=%s" % avail)

# NOT `0` when unavailable: -1 is the sentinel for "not measured", so that a
# later reader cannot confuse it with a measured absence of cards.
if avail:
    try:
        print("device.cuda_device_count=%d" % torch.cuda.device_count())
        print("device.cuda_device0=%s" % torch.cuda.get_device_name(0))
    except Exception as exc:                                     # noqa: BLE001
        print("device.cuda_device_count=ERROR (%s: %s)" % (type(exc).__name__, exc))
    print("device.device=cuda")
else:
    print("device.cuda_device_count=-1  # UNMEASURED: is_available() was False,"
          " so device_count() was never read. -1 is a sentinel, not a reading.")
    print("device.device=cpu")

try:
    print("device.torch_num_threads=%d" % torch.get_num_threads())
except Exception as exc:                                         # noqa: BLE001
    print("device.torch_num_threads=ERROR (%s)" % type(exc).__name__)

# A CPU run's wall-clock is thread-sensitive, so the thread count is part of the
# reproducibility record rather than a curiosity.
for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    print("device.env.%s=%s" % (var, os.environ.get(var, "<unset>")))
print("--- end device block ---")
