#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_data.py -- stage the CIS datasets on the pod and report what each one
actually contains (schema + real date coverage), so the experiment design is
driven by verified coverage instead of assumed coverage.

Design notes
------------
* archive.org is unreachable from this pod on both the direct and proxied route,
  so Gwern's canonical 50GB DNM archive (IA item) is out of scope. What *is*
  reachable is his own HTTP tree under gwern.net/doc/darknet-market/, which
  carries per-market archives.
* Elliptic++ ships its CSVs through Git-LFS; the GitHub tarball contains pointer
  stubs, so the real objects are fetched through the public LFS batch API.
* Everything is idempotent and hash-logged; nothing is overwritten silently.
"""
from __future__ import annotations

import csv
import hashlib
import json
import lzma
import os
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

DATA = "/root/cis/data"
RAW = os.path.join(DATA, "raw")
ELL = os.path.join(DATA, "EllipticPlusPlus-main")
PROXY = "http://mihomo.kube-system.svc.cluster.local:7890"
MANIFEST = os.path.join(DATA, "_recon", "acquisition_manifest.json")

GW = "https://gwern.net/doc/darknet-market"
ARTEFACTS = [
    # (local name, url)
    ("agora_2014_2015.csv.xz", f"{GW}/agora/2017-12-05-philipjames11-darknetmarketplacedataagora20142015.csv.xz"),
    ("kilos_6dnms_reviews.csv.xz", f"{GW}/2020-01-13-kilos-6dnms-reviews.csv.xz"),
    ("druglistingdataset.csv.xz", f"{GW}/dnm-archive/2021-09-30-munhouwong-kaggle-druglistingdataset.csv.xz"),
    ("hansa_valhalla.zip", f"{GW}/2016-sarahjamielewis-darkwebdatadumps-hansavalhalla.zip"),
    ("alphabay_2017-01-28.tar.xz", f"{GW}/alphabay/2017-01-28-alphabay.tar.xz"),
]


def log(*a):
    print(*a, flush=True)


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def download(url, dest, tries=4):
    """Fetch url -> dest. Direct first; the pod's proxy is a fallback only."""
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        log("  cached  %s (%d bytes)" % (os.path.basename(dest), os.path.getsize(dest)))
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    for i in range(1, tries + 1):
        for label, opener in (("direct", _opener(None)), ("proxy", _opener(PROXY))):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "curl/8.5.0"})
                with opener.open(req, timeout=180) as r, open(tmp, "wb") as out:
                    while True:
                        b = r.read(1 << 20)
                        if not b:
                            break
                        out.write(b)
                if os.path.getsize(tmp) == 0:
                    raise IOError("empty body")
                os.replace(tmp, dest)
                log("  got     %s (%d bytes, %s)" % (os.path.basename(dest), os.path.getsize(dest), label))
                return dest
            except Exception as e:  # noqa: BLE001
                log("  retry %d/%d %-6s %s: %s" % (i, tries, label, os.path.basename(dest), e))
    raise SystemExit("FATAL: cannot download %s" % url)


def _opener(proxy):
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def sniff_csv(path, max_rows=400000):
    """Return (n_rows, header, first_row, counter over up to 3 columns)."""
    n, header, first = 0, None, None
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        rd = csv.reader(fh)
        for row in rd:
            if not row or not any(c.strip() for c in row):
                continue
            if header is None:
                header, first = row, None
                continue
            if first is None:
                first = row
            n += 1
            if n >= max_rows:
                break
    return n, header, first


def report_table(path, label=None, max_rows=400000):
    try:
        n, header, first = sniff_csv(path, max_rows)
    except Exception as e:  # noqa: BLE001
        log("  ! %s unreadable as csv: %s" % (path, e))
        return None
    log("  --- %s ---" % (label or os.path.basename(path)))
    log("      size   : %d bytes   data rows: %d%s" % (os.path.getsize(path), n, "+" if n >= max_rows else ""))
    log("      header : %s" % (", ".join((header or [])[:16])))
    if first:
        log("      row0   : %s" % (", ".join(first[:12])[:220]))
    return header


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    manifest = {}
    if os.path.exists(MANIFEST):
        manifest = json.load(open(MANIFEST))

    log("=============== A. Gwern DNM artefacts ===============")
    for name, url in ARTEFACTS:
        dest = os.path.join(RAW, name)
        try:
            download(url, dest)
        except SystemExit as e:
            log("  SKIP %s: %s" % (name, e))
            continue
        manifest[name] = {"url": url, "bytes": os.path.getsize(dest), "sha256": sha256_file(dest)}
        # unpack into a per-artefact directory (xz/zip/tar.xz autodetected)
        stem = name
        for suf in (".tar.xz", ".csv.xz", ".zip", ".xz", ".gz", ".tar"):
            if stem.endswith(suf):
                stem = stem[: -len(suf)]
                break
        outdir = os.path.join(DATA, "extracted", stem)
        os.makedirs(outdir, exist_ok=True)
        if not os.listdir(outdir):
            log("  unpacking %s -> %s" % (name, outdir))
            try:
                if name.endswith(".tar.xz"):
                    with tarfile.open(dest, "r:xz") as tf:
                        tf.extractall(outdir)
                elif name.endswith(".csv.xz"):
                    with lzma.open(dest, "rt", encoding="utf-8", errors="replace") as src, \
                         open(os.path.join(outdir, stem + ".csv"), "w", encoding="utf-8", newline="") as dst:
                        dst.write(src.read())
                elif name.endswith(".zip"):
                    with zipfile.ZipFile(dest) as zf:
                        zf.extractall(outdir)
                else:
                    log("  (no unpacker for %s)" % name)
            except Exception as e:  # noqa: BLE001
                log("  ! unpack failed: %s: %s" % (type(e).__name__, e))
        log("      extracted: %d files" % sum(len(f) for _, _, f in os.walk(outdir)))
        for r, _d, fs in os.walk(outdir):
            for f in sorted(fs)[:12]:
                p = os.path.join(r, f)
                log("        %-58s %10d" % (os.path.relpath(p, outdir)[:58], os.path.getsize(p)))

    log("")
    log("=============== B. Gwern artefact schemas ===============")
    for stem in sorted(os.listdir(os.path.join(DATA, "extracted")) if os.path.isdir(os.path.join(DATA, "extracted")) else []):
        base = os.path.join(DATA, "extracted", stem)
        csvs = []
        for r, _d, fs in os.walk(base):
            csvs += [os.path.join(r, f) for f in fs if f.lower().endswith((".csv", ".txt"))]
        for c in sorted(csvs, key=lambda p: -os.path.getsize(p))[:4]:
            if os.path.getsize(c) < 200:
                continue
            report_table(c, label="%s :: %s" % (stem, os.path.relpath(c, base)))

    log("")
    log("=============== C. Elliptic++ real objects via Git-LFS ===============")
    ell_ok = fetch_elliptic_lfs()

    with open(MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    log("")
    log("manifest -> %s (%d artefacts)" % (MANIFEST, len(manifest)))
    if not ell_ok:
        # ★ C-220: a partial data layer must not exit 0. Section A above is complete and
        # hash-verified; Elliptic++ is absent. Printing DONE here is exactly what made a
        # missing tree read as a present one.
        log("=============== INCOMPLETE -- Elliptic++ NOT materialised ===============")
        return 1
    log("=============== DONE ===============")
    return 0


def fetch_elliptic_lfs():
    """Public repos serve LFS objects through the batch API with no credentials.

    ★ C-220 (2026-09-24). This branch used to report SUCCESS on a machine where the tree
    did not exist at all: `os.walk` over a missing directory yields nothing, so `pointers`
    stayed empty and the code logged "no LFS pointers found (data may already be
    materialised)" -- collapsing "I could not look" and "there is nothing to fetch" into
    ONE return value, which is this project's cardinal sin.

    Measured on the new pod 2026-09-24: `/root/cis/data/EllipticPlusPlus-main` did not
    exist (0 files) while the log printed `=============== DONE ===============` and the
    process exited 0. A reader would have concluded the data was there.

    The three states are now separated, and only one of them reads as success.
    """
    if not os.path.isdir(ELL):
        log("  !! NOT MATERIALISED: %s does not exist." % ELL)
        log("  !! The GitHub tarball step never produced the tree, so there was nothing to")
        log("  !! scan for pointers. This is NOT 'already materialised' (C-220).")
        return False
    pointers = []
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
                    oid = line.split(":")[1].strip()
                if line.startswith("size "):
                    size = int(line.split()[1])
            if oid and size:
                pointers.append({"path": p, "oid": oid, "size": size})

    if not pointers:
        csvs = [os.path.join(r, f) for r, _d, fs in os.walk(ELL)
                for f in fs if f.lower().endswith(".csv")]
        if not csvs:
            log("  !! %s exists but contains NO .csv at all -- refusing to call this"
                " 'materialised' (C-220)." % ELL)
            return False
        log("  no LFS pointers found; %d .csv present and none of them is a pointer"
            " => genuinely already materialised" % len(csvs))
        return True

    log("  %d LFS objects, %.1f MB total" % (len(pointers), sum(p["size"] for p in pointers) / 1e6))
    batch_url = "https://github.com/git-disl/EllipticPlusPlus.git/info/lfs/objects/batch"
    body = json.dumps({
        "operation": "download",
        "transfers": ["basic"],
        "objects": [{"oid": p["oid"], "size": p["size"]} for p in pointers],
    }).encode()
    req = urllib.request.Request(
        batch_url, data=body,
        headers={"Accept": "application/vnd.git-lfs+json",
                 "Content-Type": "application/vnd.git-lfs+json",
                 "User-Agent": "curl/8.5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        log("  ! LFS batch failed: %s: %s" % (type(e).__name__, e))
        return False
    objs = {o["oid"]: o for o in resp.get("objects", [])}
    log("  batch returned %d objects" % len(objs))
    for p in pointers:
        o = objs.get(p["oid"])
        if not o or "actions" not in o:
            log("  ! no download action for %s" % os.path.relpath(p["path"], ELL))
            continue
        href = o["actions"]["download"]["href"]
        cache = os.path.join(DATA, "lfs_cache", p["oid"])
        download(href, cache)
        got = sha256_file(cache)
        if got != p["oid"]:
            log("  ! OID MISMATCH for %s: %s" % (p["path"], got))
            continue
        os.replace(cache, p["path"])
        log("  materialised %-58s %10d bytes (oid verified)" % (os.path.relpath(p["path"], ELL)[:58], p["size"]))
    return True


if __name__ == "__main__":
    sys.exit(main())
