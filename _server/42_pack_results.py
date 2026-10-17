#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""42_pack_results.py -- POD-SIDE. Pack results/ for transfer. Nothing else.

Why this file is so small. Its predecessor 42_sync_results.py tried to
regenerate the sha256 manifest HERE, on the pod, and it crashed:

    FileNotFoundError: '/root/cis/_logs/results_manifest.sha256'

That crash was informative rather than annoying. The manifest is a LOCAL
artifact -- it lives at D:\\CIS\\_logs\\results_manifest.sha256 and does not
exist on the pod at all. So the earlier file had the two sides of the boundary
the wrong way round: it was computing the integrity record on the machine that
the record is supposed to be an independent check OF.

  pod side   : produce bytes.                        (this file)
  local side : hash the bytes it received, and diff.  (_tools/verify_results.py)

Keeping them separate is not tidiness. A manifest computed on the pod and
carried over with the tarball would be checked against itself; the only reason
the local manifest means anything is that it is computed on the other side, by
different code, over bytes that arrived by a different route (paramiko/SFTP,
then tar extraction).
"""
from __future__ import annotations

import hashlib
import os
import subprocess

ROOT = "/root/cis"
RES = os.path.join(ROOT, "results")
LOGS = os.path.join(ROOT, "_logs")
TGZ = os.path.join(LOGS, "results_sync.tgz")


def main():
    os.makedirs(LOGS, exist_ok=True)
    n = sum(len(f) for _, _, f in os.walk(RES))
    print("packing %d files from %s" % (n, RES), flush=True)
    if os.path.exists(TGZ):
        os.remove(TGZ)
    r = subprocess.run(["tar", "czf", TGZ, "-C", ROOT, "results"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("TAR FAILED rc=%d %s" % (r.returncode, r.stderr[:400]))
        return
    h = hashlib.sha256(open(TGZ, "rb").read()).hexdigest()
    print("wrote %s  %.2f MB  sha256(tgz)=%s"
          % (TGZ, os.path.getsize(TGZ) / 1e6, h))
    print("PACK_DONE")


if __name__ == "__main__":
    main()
