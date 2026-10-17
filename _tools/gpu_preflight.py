#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPU preflight for the D:\\CIS pod. Prints one verdict line. Exit code is the verdict.

WHY THIS EXISTS (C-27)
----------------------
On 2026-09-24 this project lost most of a day to a pod whose GPU looked fine and
was not. `nvidia-smi` listed an RTX 4090; NVML answered every question; and
`cuInit(0)` returned 100 = CUDA_ERROR_NO_DEVICE. torch reported device_count()==1
while the CUDA driver reported 0. The card self-reported "GPU requires reset" with
Channel Repair Pending and TPC Repair Pending, and no in-container remedy existed
(nvidia-smi --gpu-reset -> Not Supported; /sys/.../reset -> Read-only file system;
see the ledger's C-27 for the exhaustive list).

The lesson is about *which instrument you believe*. NVML and the CUDA driver are
different code paths. "nvidia-smi works" is not evidence that you can compute.

So this script asks three questions in increasing order of authority, and the
verdict comes from the LAST one that can be answered:

  1. NVML      -- is there a card, what is it      (weak: true even when broken)
  2. CUDA drv  -- can the driver initialize it     (strong: this is what fails)
  3. a real op -- allocate, move, multiply         (authoritative: nothing else counts)

Question 3 is the only one that proves "you can compute". If torch is importable
we do a tiny matmul on the GPU and compare against the CPU answer; if torch is not
available we say so and the script will NOT claim COMPUTE_OK, because without
running a kernel we have not earned that claim.

USAGE
    python3 gpu_preflight.py            # verdict line on stdout, exit 0 iff COMPUTE_OK
    python3 gpu_preflight.py -v         # also print every probe result

INTERPRETATION
    COMPUTE_OK              a real GPU kernel ran and its result was correct.
    NVML_ONLY_NO_CUDA       the card is visible to NVML but the CUDA driver will not
                            initialize it. This is the C-27 signature. No in-container
                            fix. Request a pod restart from the console -- and say in
                            the request that re-attaching the same degraded card will
                            not help.
    NO_DEVICE               nothing visible at all.
    NO_TORCH                hardware may be fine; we cannot test it. Install torch and
                            re-run. Do not treat as pass.
"""

import ctypes
import os
import subprocess
import sys

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv
_results = {}


def log(msg):
    if VERBOSE:
        print("    " + msg)


def probe_nvml():
    """NVML view: what the driver advertises. Weak evidence -- see module docstring."""
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,uuid,pci.bus_id,driver_version,memory.total",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        _results["nvml"] = ("absent", "nvidia-smi not on PATH")
        return
    except Exception as exc:                                   # noqa: BLE001
        _results["nvml"] = ("error", "%s: %s" % (type(exc).__name__, exc))
        return

    rows = [r for r in (out.stdout or "").strip().splitlines() if r.strip()]
    if not rows:
        _results["nvml"] = ("none", "nvidia-smi returned no rows (rc=%d)" % out.returncode)
        return
    _results["nvml"] = ("listed", "%d card(s)" % len(rows))
    for r in rows:
        log("nvml: " + r)

    # The degradation markers. Recorded separately because they are the thing that
    # told us WHY cuInit failed, back when nothing else did.
    try:
        q = subprocess.run(["nvidia-smi", "-q"], capture_output=True, text=True, timeout=60)
        text = q.stdout or ""
        markers = [m for m in ("GPU requires reset",
                               "Channel Repair Pending",
                               "TPC Repair Pending")
                   if m in text]
        if markers:
            _results["nvml_health"] = ("repair_pending", ", ".join(markers))
            for m in markers:
                log("health: %s" % m)
        else:
            _results["nvml_health"] = ("clean", "no repair-pending markers")
    except Exception as exc:                                   # noqa: BLE001
        _results["nvml_health"] = ("unknown", "%s: %s" % (type(exc).__name__, exc))


def probe_cuda_driver():
    """CUDA driver API. This is the code path that failed with error 100."""
    for name in ("libcuda.so.1", "libcuda.so", "libcuda.dylib", "nvcuda.dll"):
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            continue
        try:
            rc = lib.cuInit(ctypes.c_uint(0))
        except Exception as exc:                               # noqa: BLE001
            _results["cuda_driver"] = ("error", "%s: %s" % (type(exc).__name__, exc))
            return
        # 0 = CUDA_SUCCESS, 100 = CUDA_ERROR_NO_DEVICE. Report the number as-is:
        # the number is the evidence, the name is my convenience.
        n = ctypes.c_int(-1)
        rc2 = lib.cuDeviceGetCount(ctypes.byref(n))
        _results["cuda_driver"] = (
            "ok" if rc == 0 and n.value > 0 else "fail",
            "cuInit rc=%d, cuDeviceGetCount rc=%d n=%d (lib=%s)" % (rc, rc2, n.value, name),
        )
        log("cuda: cuInit rc=%d  cuDeviceGetCount rc=%d n=%d  [%s]"
            % (rc, rc2, n.value, name))
        return
    _results["cuda_driver"] = ("absent", "no libcuda found")


def probe_real_op():
    """The authoritative probe: allocate on the GPU, run a kernel, check the answer.

    A card that can be enumerated but not computed on passes probes 1 and 2 and
    fails here. This is the only probe whose success licenses COMPUTE_OK.
    """
    try:
        import torch
    except ImportError as exc:
        _results["torch"] = ("absent", str(exc))
        return
    _results["torch"] = ("present", torch.__version__)
    log("torch: %s" % torch.__version__)

    try:
        avail = torch.cuda.is_available()
    except Exception as exc:                                   # noqa: BLE001
        _results["torch_cuda"] = ("error", "%s: %s" % (type(exc).__name__, exc))
        return
    _results["torch_cuda"] = ("available" if avail else "unavailable",
                              "torch.cuda.is_available() == %s" % avail)
    log("torch.cuda.is_available() = %s" % avail)
    if not avail:
        return

    try:
        n = torch.cuda.device_count()
        _results["torch_count"] = ("ok", "device_count=%d" % n)
        log("torch.cuda.device_count() = %d" % n)
        if n < 1:
            return
    except Exception as exc:                                   # noqa: BLE001
        _results["torch_count"] = ("error", "%s: %s" % (type(exc).__name__, exc))
        return

    # The part that actually counts. 64x64 float32 matmul; compare to CPU exactly.
    try:
        a = torch.arange(64 * 64, dtype=torch.float32).reshape(64, 64) % 7.0
        b = a.t().contiguous()
        cpu = (a @ b)
        dev = (a.cuda() @ b.cuda()).cpu()
        same = bool(torch.equal(cpu, dev))
        _results["kernel"] = ("ok" if same else "wrong",
                              "64x64 matmul ran on GPU; matches CPU == %s" % same)
        log("kernel: 64x64 matmul on cuda:%s, matches CPU == %s"
            % (torch.cuda.get_device_name(0) if n else "?", same))
        if same:
            # Report the identity of the card we actually computed on, so a later
            # claim about "the GPU" can be tied to a specific device.
            try:
                _results["compute_device"] = (
                    "ok",
                    "%s uuid=%s" % (torch.cuda.get_device_name(0),
                                    getattr(torch.cuda.get_device_properties(0),
                                            "uuid", "?")),
                )
                log("compute device: %s" % (_results["compute_device"][1]))
            except Exception:                                  # noqa: BLE001
                pass
    except Exception as exc:                                   # noqa: BLE001
        _results["kernel"] = ("error", "%s: %s" % (type(exc).__name__, exc))
        log("kernel: raised %s: %s" % (type(exc).__name__, exc))


def verdict():
    """One line. Ordered by decreasing authority, most authoritative answer wins."""
    if _results.get("kernel", ("", ""))[0] == "ok":
        return "COMPUTE_OK", 0
    if _results.get("kernel", ("", ""))[0] == "wrong":
        return "KERNEL_WRONG_RESULT", 4
    if _results.get("torch", ("", ""))[0] == "absent":
        # Hardware might be perfect. We did not test it, so we do not pass it.
        return "NO_TORCH", 5
    nvml = _results.get("nvml", ("", ""))[0]
    drv = _results.get("cuda_driver", ("", ""))[0]
    if nvml in ("listed",) and drv in ("fail", "absent"):
        return "NVML_ONLY_NO_CUDA", 2
    if nvml in ("none", "absent") and drv in ("fail", "absent"):
        return "NO_DEVICE", 3
    if drv == "ok":
        # Driver initializes but torch did not run a kernel -- usually a torch/CUDA
        # version mismatch, not hardware. Not a pass.
        return "CUDA_OK_TORCH_UNUSABLE", 6
    return "UNKNOWN", 7


def main():
    host = os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "?")
    print("GPU preflight -- host %s, python %s" % (host, sys.version.split()[0]))
    probe_nvml()
    probe_cuda_driver()
    probe_real_op()

    if VERBOSE:
        print()
        print("probe results:")
        for k in ("nvml", "nvml_health", "cuda_driver", "torch", "torch_cuda",
                  "torch_count", "kernel", "compute_device"):
            if k in _results:
                print("  %-14s %-14s %s" % (k, _results[k][0], _results[k][1]))
        print()

    v, code = verdict()
    print("GPU_PREFLIGHT: %s" % v)
    if v == "NVML_ONLY_NO_CUDA":
        print("  -> C-27 signature. The card is visible to NVML but the CUDA driver")
        print("     will not initialize it. No in-container remedy exists. Request a")
        print("     pod restart from the console, and state in the request that")
        print("     re-attaching the same degraded card will not help.")
    elif v == "COMPUTE_OK":
        print("  -> a real kernel ran and produced a correct answer. GPU work may proceed.")
    elif v == "NO_TORCH":
        print("  -> torch is not importable, so no kernel was run. This is NOT a pass;")
        print("     install torch and re-run.")
    return code


if __name__ == "__main__":
    sys.exit(main())
