#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""45_E10_endpoint_discovery.py -- learn how scidb.cn actually serves search.

44 guessed five API paths and every one answered 404/500. That is an answer about
my guesses, not about the dataset, so the next move is the one 44 printed: fetch
the site's own pages and read how it queries. Guess-then-check is fine; what is
not fine is letting a wrong guess rest as a finding about the world.

This does not conclude anything. It collects: the homepage, a search page, the
JS bundles they load, and any API-looking path found in any of them.
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OUT = "/root/cis/data/external/c13_recon/45_E10_endpoint_discovery.json"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

PAGES = [
    "https://www.scidb.cn/",
    "https://www.scidb.cn/search?q=%E7%94%B5%E4%BF%A1%E8%AF%88%E9%AA%97",
    "https://www.scidb.cn/s?q=%E7%94%B5%E4%BF%A1%E8%AF%88%E9%AA%97",
    "https://www.scidb.cn/oai?verb=Identify",
    "https://www.scidb.cn/api/front/search/dataset?keyword=%E8%AF%88%E9%AA%97",
    "https://www.scidb.cn/api/front/search?keyword=%E8%AF%88%E9%AA%97",
    "https://www.scidb.cn/api/front/dataSet/search?keyword=%E8%AF%88%E9%AA%97",
]

# Things worth pulling out of any body we get.
PATS = {
    "script_src": r'<script[^>]+src="([^"]+)"',
    "api_path":   r'"(/[a-zA-Z0-9_\-/]*api[a-zA-Z0-9_\-/]*)"',
    "fetch_url":  r'(?:url|baseURL|baseUrl)\s*[:=]\s*["\']([^"\']+)["\']',
    "oai":        r'<[^>]*oai[^>]*>',
}


def get(url, timeout=45):
    rec = {"url": url, "transmitted": False, "status": None, "length": None,
           "error": None, "body": None, "found": {}}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            body = r.read(600000).decode("utf-8", "replace")
            rec.update(transmitted=True, status=r.status, length=len(body),
                       body=body)
    except urllib.error.HTTPError as exc:
        rec["transmitted"] = True
        rec["status"] = exc.code
        try:
            rec["body"] = exc.read(120000).decode("utf-8", "replace")
            rec["length"] = len(rec["body"])
        except Exception:                                          # noqa: BLE001
            pass
    except Exception as exc:                                       # noqa: BLE001
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
    return rec


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "pages": [],
           "api_paths": [], "js_bundles": [], "oai_seen": False}

    for url in PAGES:
        rec = get(url)
        body = rec.pop("body") or ""
        state = ("%s len=%s" % (rec["status"], rec["length"])
                 if rec["transmitted"] else "NEVER-SENT %s" % rec["error"])
        found = {}
        for name, pat in PATS.items():
            hits = re.findall(pat, body, re.I)
            if hits:
                found[name] = sorted(set(hits))[:25]
        rec["found"] = found
        print("%-64s %s" % (url[:64], state))
        for k, v in found.items():
            print("      %-10s %s" % (k, v[:6]))
        if body:
            rec["body_head"] = body[:2500]
        out["pages"].append(rec)
        out["api_paths"] += found.get("api_path", [])
        out["js_bundles"] += found.get("script_src", [])
        if "oai" in body.lower():
            out["oai_seen"] = True

    out["api_paths"] = sorted(set(out["api_paths"]))
    out["js_bundles"] = sorted(set(out["js_bundles"]))

    # Pull the JS bundles and look for the API base inside them.
    print("\n[j] fetching %d js bundles to find the api base"
          % len(out["js_bundles"][:12]))
    bundle_finds = {}
    for src in out["js_bundles"][:12]:
        u = src if src.startswith("http") else urllib.parse.urljoin(
            "https://www.scidb.cn/", src)
        r = get(u, timeout=30)
        if not r["transmitted"] or not r["body"]:
            continue
        b = r["body"]
        hits = sorted(set(re.findall(
            r'["\'](/[a-zA-Z0-9_\-/\.]*(?:api|search)[a-zA-Z0-9_\-/\.]*)["\']', b)))
        if hits:
            bundle_finds[u] = hits[:25]
            print("   %-60s %d api-ish paths" % (u[-60:], len(hits)))
    out["bundle_finds"] = bundle_finds

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("\nwrote %s" % OUT)
    print("api paths seen: %d | js bundles: %d | oai endpoint: %s"
          % (len(out["api_paths"]), len(out["js_bundles"]), out["oai_seen"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
