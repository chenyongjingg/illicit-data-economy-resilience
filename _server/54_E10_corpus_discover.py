#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""54_E10_corpus_discover.py -- find how ScienceDB actually serves the 571-case corpus.

C-103 established the dataset EXISTS (10.57760/sciencedb.j00133.00466, "571 条电信
诈骗案例", open access). This finds the download route. It deliberately does NOT
guess-and-report-failure: every probe is three-state (transmitted / absent /
never-sent), because "my guessed URL 404s" is a fact about my guess, not about
the dataset.

Route 1: the DOI content-negotiation / landing page.
Route 2: ScienceDB's own detail API, using the UUID already recorded in the OAI
         record (alternateIdentifier a8675d31c70545ebaa54fe47f951cdb9).
Route 3: the OAI record's relatedIdentifier fields, which often carry the file URL.

Whatever is found is written out with the evidence that found it.
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

UA = "cis-sprint-corpus/1.0 (+research; contact: local)"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
DOI = "10.57760/sciencedb.j00133.00466"
UUID = "a8675d31c70545ebaa54fe47f951cdb9"
OUT = "/root/cis/results/54_E10_corpus_discover.json"


def get(url, timeout=45, accept=None):
    """Three-state fetch: says whether the request was SENT before saying no."""
    rec = {"url": url, "transmitted": False, "status": None, "bytes": None,
           "error": None, "text": None}
    hdrs = {"User-Agent": UA}
    if accept:
        hdrs["Accept"] = accept
    try:
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            b = r.read()
            rec.update(transmitted=True, status=r.status, bytes=len(b))
            rec["final_url"] = r.geturl()
            rec["content_type"] = r.headers.get("Content-Type")
            rec["text"] = b.decode("utf-8", "replace")[:200000]
        return rec
    except urllib.error.HTTPError as exc:
        rec.update(transmitted=True, status=exc.code)
        try:
            rec["text"] = exc.read().decode("utf-8", "replace")[:40000]
        except Exception:                                          # noqa: BLE001
            pass
        return rec
    except Exception as exc:                                       # noqa: BLE001
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
        return rec


def main():
    out = {"doi": DOI, "uuid": UUID, "probes": []}
    routes = [
        ("doi_landing", "https://doi.org/%s" % DOI, None),
        ("scidb_detail_uuid", "https://www.scidb.cn/api/dataSet/detail?id=%s" % UUID, "application/json"),
        ("scidb_detail_doi", "https://www.scidb.cn/api/dataSet/detail?doi=%s" % DOI, "application/json"),
        ("scidb_page", "https://www.scidb.cn/en/detail?dataSetId=%s" % UUID, None),
    ]
    for name, url, acc in routes:
        r = get(url, accept=acc)
        print("[%-18s] sent=%s status=%s bytes=%s %s"
              % (name, r["transmitted"], r["status"], r["bytes"],
                 r["error"] or (r.get("final_url") or "")[:90]))
        txt = r.get("text") or ""
        urls = []
        if txt:
            # Any file-ish link the page/API exposes.
            urls = sorted(set(re.findall(
                r'https?://[^\s"\'<>]*?/(?:download|file|api)[^\s"\'<>]{0,180}', txt)))[:25]
            if urls:
                print("     candidate file routes: %d" % len(urls))
                for u in urls[:8]:
                    print("        %s" % u[:150])
            for key in ("fileName", "fileId", "downloadUrl", "url"):
                for m in re.findall(r'"%s"\s*:\s*"([^"]{1,200})"' % key, txt)[:5]:
                    print("     %-12s %s" % (key, m[:140]))
        out["probes"].append({k: r.get(k) for k in
                              ("url", "transmitted", "status", "bytes",
                               "error", "final_url", "content_type")}
                             | {"candidate_urls": urls[:25]})
        time.sleep(0.5)

    os.makedirs("/root/cis/results", exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    import os
    sys.exit(main())
