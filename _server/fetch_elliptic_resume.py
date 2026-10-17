#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_elliptic_resume.py -- materialise the Elliptic++ Git-LFS objects with
byte-range resume.

Why a second fetcher exists (the first is `fetch_data.py:fetch_elliptic_lfs`):
that one opens the destination with "wb" and has no Range support, so any
interruption restarts the object from zero. Observed on this pod: a
355,467,264-byte partial was discarded and the object restarted at 64 MiB. On a
link measured at ~0.367 MB/s for these hosts, the two remaining objects are
609 MB and 695 MB -- roughly 30 and 33 minutes of *uninterrupted* transfer each.
A downloader that cannot resume cannot finish them.

Correctness is unchanged by resuming: the LFS OID is a SHA-256 of the object's
content, and it is verified over the *whole assembled file* before the file is
moved into place. A truncated or mis-offset resume therefore fails the OID check
and is rejected rather than silently accepted. The partial is kept on disk
between attempts, so a rejected object still makes forward progress.

Idempotent: objects already materialised and OID-clean are skipped.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

DATA = "/root/cis/data"
ELL = os.path.join(DATA, "EllipticPlusPlus-main")
CACHE = os.path.join(DATA, "lfs_cache")
BATCH = "https://github.com/git-disl/EllipticPlusPlus.git/info/lfs/objects/batch"
PROXY = "http://mihomo.kube-system.svc.cluster.local:7890"
UA = "curl/8.5.0"
CHUNK = 1 << 20
MAX_ATTEMPTS = 40


def log(*a):
    print(" ".join(str(x) for x in a), flush=True)


def opener(proxy):
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def find_pointers():
    out = []
    for r, _d, fs in os.walk(ELL):
        for f in fs:
            if not f.lower().endswith(".csv"):
                continue
            p = os.path.join(r, f)
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                head = fh.read(400)
            if "git-lfs.github.com/spec/v1" not in head:
                continue
            oid = size = None
            for line in head.splitlines():
                if line.startswith("oid sha256:"):
                    oid = line.split(":", 1)[1].strip()
                elif line.startswith("size "):
                    size = int(line.split()[1])
            if oid and size:
                out.append({"path": p, "oid": oid, "size": size})
    return out


def batch_hrefs(pointers):
    body = json.dumps({
        "operation": "download",
        "transfers": ["basic"],
        "objects": [{"oid": p["oid"], "size": p["size"]} for p in pointers],
    }).encode()
    req = urllib.request.Request(
        BATCH, data=body,
        headers={"Accept": "application/vnd.git-lfs+json",
                 "Content-Type": "application/vnd.git-lfs+json",
                 "User-Agent": UA})
    # The batch endpoint needs the proxy (github.com is unreachable direct).
    with opener(PROXY).open(req, timeout=120) as r:
        resp = json.loads(r.read())
    return {o["oid"]: o for o in resp.get("objects", [])}


def fetch_resumable(href, dest):
    """Append to `dest` using HTTP Range until the full object is present.

    Returns (bytes_now, total). Raises on unrecoverable failure.
    """
    total = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        have = os.path.getsize(dest) if os.path.exists(dest) else 0
        headers = {"User-Agent": UA}
        if have:
            headers["Range"] = "bytes=%d-" % have
        opener_ = opener(None) if attempt % 2 else opener(PROXY)
        label = "direct" if attempt % 2 else "proxy"
        try:
            req = urllib.request.Request(href, headers=headers)
            with opener_.open(req, timeout=180) as r:
                code = r.getcode()
                if total is None:
                    cr = r.headers.get("Content-Range")
                    if cr and "/" in cr:
                        total = int(cr.split("/")[-1])
                    else:
                        total = have + int(r.headers.get("Content-Length") or 0)
                # A server that ignores Range replies 200 with the whole body.
                mode = "ab" if (have and code == 206) else "wb"
                if mode == "wb":
                    have = 0
                got = 0
                with open(dest, mode) as out:
                    while True:
                        b = r.read(CHUNK)
                        if not b:
                            break
                        out.write(b)
                        got += len(b)
            now = os.path.getsize(dest)
            log("    %-6s attempt %2d: +%d B -> %d / %s"
                % (label, attempt, got, now, total if total else "?"))
            if total and now >= total:
                return now, total
            time.sleep(1)
        except Exception as e:  # noqa: BLE001
            now = os.path.getsize(dest) if os.path.exists(dest) else 0
            log("    %-6s attempt %2d failed at %d B: %s: %s"
                % (label, attempt, now, type(e).__name__, str(e)[:90]))
            time.sleep(3)
    raise SystemExit("FATAL: exhausted attempts for %s" % dest)


def main():
    os.makedirs(CACHE, exist_ok=True)
    pointers = find_pointers()
    if not pointers:
        log("all Elliptic++ objects already materialised")
        return 0
    log("%d LFS object(s) outstanding, %.1f MB total"
        % (len(pointers), sum(p["size"] for p in pointers) / 1e6))

    objs = batch_hrefs(pointers)
    done_all = True
    for p in pointers:
        rel = os.path.relpath(p["path"], ELL)
        o = objs.get(p["oid"])
        if not o or "actions" not in o:
            log("  ! no download action for %s" % rel)
            done_all = False
            continue
        href = o["actions"]["download"]["href"]
        dest = os.path.join(CACHE, p["oid"] + ".part")
        log("  --> %s  (%.1f MB)" % (rel, p["size"] / 1e6))
        try:
            now, total = fetch_resumable(href, dest)
        except SystemExit as e:
            log("  ! %s" % e)
            done_all = False
            continue
        if os.path.getsize(dest) != p["size"]:
            log("  ! size mismatch %s: have %d want %d"
                % (rel, os.path.getsize(dest), p["size"]))
            done_all = False
            continue
        got = sha256_file(dest)
        if got != p["oid"]:
            # The OID is the content hash; a mismatch means the assembled bytes
            # are wrong. Discard so the next run restarts cleanly rather than
            # appending onto a corrupt base forever.
            log("  ! OID MISMATCH %s\n      have %s\n      want %s -- discarding partial"
                % (rel, got, p["oid"]))
            os.remove(dest)
            done_all = False
            continue
        with open(p["path"], "w", encoding="utf-8") as fh:
            pass  # replace the pointer with the real file
        os.replace(dest, p["path"])
        log("  OK  materialised %s (%d bytes, OID verified)" % (rel, p["size"]))

    log("REMAINING=%d" % len(find_pointers()))
    return 0 if done_all else 1


if __name__ == "__main__":
    sys.exit(main())
