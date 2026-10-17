#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""61_E10_api_context.py -- read the API call sites out of ScienceDB's own bundle.

60_ recovered the API family (`api/sdb-dataset-service/...`) but the paths are
assembled by string concatenation in the client, so a bare endpoint name is not
the whole URL. This prints the surrounding source of each mention, which shows
how the URL is built and which verb/params it takes -- reading the client's own
code instead of guessing shapes at it.
"""
import json
import re
import ssl
import sys
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
BASE = "https://www.scidb.cn"
BUNDLES = ["/_nuxt/343d80e.js", "/_nuxt/97138fb.js"]


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                    timeout=45, context=CTX) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as exc:                                     # noqa: BLE001
        print("  fetch failed %s: %s" % (url, exc))
        return ""


def main():
    for b in BUNDLES:
        js = get(BASE + b)
        print("\n=== %s (%d chars) ===" % (b, len(js)))
        for pat, label in ((r"sdb-dataset-service/[A-Za-z0-9_\-/\.]{0,40}", "DATASET-SVC"),
                           (r"[\"'`][^\"'`]{0,60}file[^\"'`]{0,60}[\"'`]", "FILE"),
                           (r"download[^\"'`,;)]{0,80}", "DOWNLOAD")):
            hits = []
            for m in re.finditer(pat, js, re.I):
                s = max(0, m.start() - 70)
                hits.append(js[s:m.end() + 90].replace("\n", " "))
            seen, uniq = set(), []
            for h in hits:
                if h not in seen:
                    seen.add(h)
                    uniq.append(h)
            print("  -- %s: %d unique" % (label, len(uniq)))
            for h in uniq[:14]:
                print("     %s" % h[:190])
    return 0


if __name__ == "__main__":
    sys.exit(main())
