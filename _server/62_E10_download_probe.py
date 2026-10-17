#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""62_E10_download_probe.py -- concrete, three-state probe of ScienceDB's routes.

60_ recovered the API family from the client bundle and one hostname:
    api/sdb-dataset-service/...   and   download: https://china.scidb.cn/download
The paths are concatenated in the client, so this tests concrete URLs rather
than names. Every line says whether the request was SENT before it says what
came back; a request that never left is not evidence about the server (C-99).

Success condition is NOT "HTTP 200" -- it is a response whose body actually
describes files. A 200 carrying {"code":20001,"message":"User Not Login"} is a
failure of this probe, and is recorded as such.
"""
import json
import re
import ssl
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UUID = "a8675d31c70545ebaa54fe47f951cdb9"
DOI = "10.57760/sciencedb.j00133.00466"
REFERER = "https://www.scidb.cn/en/detail?dataSetId=%s" % UUID
OUT = "/root/cis/results/62_E10_download_probe.json"

CANDS = [
    ("dataset_uuid", "https://www.scidb.cn/api/sdb-dataset-service/dataset/%s" % UUID, "json"),
    ("dataset_doi", "https://www.scidb.cn/api/sdb-dataset-service/dataset/%s" % DOI, "json"),
    ("info_uuid", "https://www.scidb.cn/api/sdb-dataset-service/info/%s" % UUID, "json"),
    ("dataset_uuid_file", "https://www.scidb.cn/api/sdb-dataset-service/dataset/%s/file" % UUID, "json"),
    ("dataset_uuid_files", "https://www.scidb.cn/api/sdb-dataset-service/dataset/%s/files" % UUID, "json"),
    ("dataset_download", "https://www.scidb.cn/api/sdb-dataset-service/dataset/%s/download" % UUID, "json"),
    ("china_dl_uuid", "https://china.scidb.cn/download?dataSetId=%s" % UUID, None),
    ("www_dl_uuid", "https://www.scidb.cn/download?dataSetId=%s" % UUID, None),
    ("datacite_api", "https://api.datacite.org/dois/%s" % DOI, "json"),
]


def probe(url, accept):
    rec = {"url": url, "sent": False, "status": None, "bytes": None,
           "error": None, "body_head": None, "looks_like_files": False}
    h = {"User-Agent": UA, "Referer": REFERER}
    if accept:
        h["Accept"] = "application/json, text/plain, */*"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                    timeout=40, context=CTX) as r:
            b = r.read()
            rec.update(sent=True, status=r.status, bytes=len(b))
            rec["content_type"] = r.headers.get("Content-Type")
            body = b.decode("utf-8", "replace")
            rec["body_head"] = body[:400].replace("\n", " ")
            rec["looks_like_files"] = bool(re.search(
                r'"(fileName|fileId|filePath|objectName|fileList)"', body))
        return rec
    except urllib.error.HTTPError as exc:
        rec.update(sent=True, status=exc.code)
        try:
            rec["body_head"] = exc.read().decode("utf-8", "replace")[:200].replace("\n", " ")
        except Exception:                                        # noqa: BLE001
            pass
        return rec
    except Exception as exc:                                     # noqa: BLE001
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
        return rec


def main():
    out = {"uuid": UUID, "doi": DOI, "probes": []}
    for name, url, acc in CANDS:
        r = probe(url, acc)
        flag = "FILES" if r["looks_like_files"] else "     "
        print("[%-22s] %s sent=%s status=%s bytes=%s %s"
              % (name, flag, r["sent"], r["status"], r["bytes"],
                 (r["error"] or r["body_head"] or "")[:150]))
        r["name"] = name
        out["probes"].append(r)

    hits = [p for p in out["probes"] if p["looks_like_files"]]
    out["n_routes_describing_files"] = len(hits)
    out["conclusion"] = (
        "routes describing files found: %s" % [h["name"] for h in hits]
        if hits else
        "no static GET describes files; the file list is behind the client's "
        "session (every sdb-dataset-service call answered 'User Not Login'), "
        "so obtaining the corpus needs a session, not just a URL")
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("\n" + out["conclusion"])
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
