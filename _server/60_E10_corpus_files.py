#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""60_E10_corpus_files.py -- find the actual file list for the 571-case corpus.

54_ found the landing page (200, 784 KB) but no file URLs: ScienceDB's detail
page is a JS app, so the file list is not in the HTML that arrives first.

This reads the page's OWN vocabulary instead of guessing endpoints -- the bundle
names its API paths, and those names are evidence about where the data lives in
a way my guesses are not. Everything is three-state: a request that was never
sent is never reported as a 404.

If a file list is found, the files are downloaded with the completeness check
this project requires (bytes == Content-Length AND a real trailer), because a
truncated download that "succeeded" is the failure mode already recorded once
(C-99).
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UUID = "a8675d31c70545ebaa54fe47f951cdb9"
PAGE = "https://www.scidb.cn/en/detail?dataSetId=%s" % UUID
OUT = "/root/cis/results/60_E10_corpus_files.json"


def fetch(url, timeout=45, accept=None, referer=None):
    rec = {"url": url, "sent": False, "status": None, "bytes": None,
           "error": None}
    h = {"User-Agent": UA}
    if accept:
        h["Accept"] = accept
    if referer:
        h["Referer"] = referer
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                    timeout=timeout, context=CTX) as r:
            b = r.read()
            rec.update(sent=True, status=r.status, bytes=len(b),
                       content_type=r.headers.get("Content-Type"),
                       text=b.decode("utf-8", "replace"))
        return rec
    except urllib.error.HTTPError as exc:
        rec.update(sent=True, status=exc.code)
        try:
            rec["text"] = exc.read().decode("utf-8", "replace")[:20000]
        except Exception:                                        # noqa: BLE001
            pass
        return rec
    except Exception as exc:                                     # noqa: BLE001
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
        return rec


def main():
    out = {"uuid": UUID, "page": PAGE, "api_paths": [], "tried": [], "files": []}
    p = fetch(PAGE)
    print("landing: sent=%s status=%s bytes=%s" % (p["sent"], p["status"], p["bytes"]))
    html = p.get("text") or ""

    # The app's own vocabulary for its endpoints.
    apis = sorted(set(re.findall(r'["\'/](api/[A-Za-z0-9_\-/\.]{3,60})["\']', html)))
    print("api paths named in the page: %d" % len(apis))
    for a in apis[:40]:
        print("   %s" % a)
    out["api_paths"] = apis

    # Script bundles: the file-list call is usually named in one of them.
    js = sorted(set(re.findall(r'src="([^"]+\.js[^"]*)"', html)))
    print("script bundles: %d" % len(js))
    for j in js[:12]:
        u = j if j.startswith("http") else ("https://www.scidb.cn" + ("" if j.startswith("/") else "/") + j)
        r = fetch(u, timeout=40)
        found = sorted(set(re.findall(
            r'["\'/](api/[A-Za-z0-9_\-/\.]{3,60})["\']', r.get("text") or "")))
        if found:
            print("   %s -> %d api refs: %s" % (j[:60], len(found), found[:12]))
            apis.extend(found)
        time.sleep(0.2)
    apis = sorted(set(apis))
    out["api_paths"] = apis

    # Try the plausible ones for a file listing.
    guesses = [a for a in apis if re.search(r"file|dataset|resource|download", a, re.I)]
    for a in (["api/dataSet/fileList", "api/dataSet/getFileList",
               "api/dataSet/download", "api/file/list", "api/dataSet/files"]
              + guesses[:20]):
        if a.startswith("http"):
            continue
        for sep in ("?", "/"):
            url = ("https://www.scidb.cn/%s%sdataSetId=%s"
                   % (a, sep, UUID))
            r = fetch(url, accept="application/json", referer=PAGE)
            body = (r.get("text") or "")[:300].replace("\n", " ")
            print("  [%-34s] sent=%s status=%s bytes=%s %s"
                  % (a + sep, r["sent"], r["status"], r["bytes"], body[:120]))
            out["tried"].append({"url": url, "sent": r["sent"],
                                 "status": r["status"], "bytes": r["bytes"],
                                 "head": body})
            if r["sent"] and r["status"] == 200 and (r["bytes"] or 0) > 50:
                break
        time.sleep(0.2)

    os.makedirs("/root/cis/results", exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
