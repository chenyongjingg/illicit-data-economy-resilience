#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""46_E10_oai_harvest.py -- enumerate ScienceDB's actual holdings via OAI-PMH.

WHY
    44 guessed search APIs and got 404s. 45 found that scidb.cn serves OAI-PMH
    at /oai, which is strictly better for this question: OAI-PMH enumerates the
    repository's real records, so "is the 571-case dataset in ScienceDB?" stops
    depending on whether my keyword happened to match their tokeniser.

    This is the authoritative route. A keyword search that misses tells you about
    the search; a full enumeration that misses tells you about the holdings.

STAGES
    1. Identify / ListMetadataFormats / ListSets  -- learn the repository's shape
    2. one page of ListRecords  -- measure total size before committing to harvest
    3. harvest titles (bounded by --max), grepping for 诈骗 / 电信诈骗 / 571

    Sizes are measured before the expensive step, not discovered by running it.
"""
import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.scidb.cn/oai"
OUTDIR = "/root/cis/data/external/c13_recon"
UA = "cis-sprint-oai-harvester/1.0 (+research; contact: local)"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# Terms that would identify the plan's dataset, and a couple that would identify
# a near neighbour (so a miss is informative: if 诈骗 hits nothing at all, the
# repository simply does not carry this genre, which is a different finding from
# "it carries the genre but not this dataset").
TERMS = ["电信诈骗", "诈骗", "网络诈骗", "角色标注", "571", "fraud", "scam"]


def oai(params, timeout=60, tries=3):
    """One OAI-PMH verb call. Records the HTTP answer so an empty result can be
    told apart from a failed request."""
    url = BASE + "?" + urllib.parse.urlencode(params)
    last = None
    for a in range(tries):
        rec = {"url": url, "transmitted": False, "status": None,
               "error": None, "xml": None, "bytes": None}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                body = r.read().decode("utf-8", "replace")
                rec.update(transmitted=True, status=r.status, xml=body,
                           bytes=len(body))
            return rec
        except urllib.error.HTTPError as exc:
            rec["transmitted"] = True
            rec["status"] = exc.code
            try:
                rec["xml"] = exc.read().decode("utf-8", "replace")
            except Exception:                                      # noqa: BLE001
                pass
            return rec
        except Exception as exc:                                   # noqa: BLE001
            rec["error"] = "%s: %s" % (type(exc).__name__, exc)
            last = rec
            time.sleep(2 * (a + 1))
    return last


def tag(xml, name):
    m = re.search(r"<%s[^>]*>(.*?)</%s>" % (name, name), xml, re.S | re.I)
    return m.group(1).strip() if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=4000,
                    help="max records to harvest (safety bound)")
    ap.add_argument("--pages", type=int, default=200, help="max ListRecords pages")
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": {}}

    # ---- 1. repository shape -------------------------------------------------
    print("[1] Identify")
    r = oai({"verb": "Identify"})
    if not r["transmitted"]:
        print("   NEVER-SENT %s -- cannot proceed; this is a transport failure, "
              "not an empty repository" % r["error"])
        return 2
    for f in ("repositoryName", "baseURL", "earliestDatestamp",
              "deletedRecord", "granularity"):
        print("   %-16s %s" % (f, tag(r["xml"] or "", f)))
    out["steps"]["identify"] = {"repositoryName": tag(r["xml"], "repositoryName"),
                                "earliestDatestamp": tag(r["xml"], "earliestDatestamp"),
                                "status": r["status"]}

    print("\n[2] ListMetadataFormats")
    r = oai({"verb": "ListMetadataFormats"})
    prefixes = re.findall(r"<metadataPrefix>([^<]+)</metadataPrefix>",
                          r["xml"] or "")
    print("   prefixes: %s" % (prefixes or "NONE"))
    out["steps"]["formats"] = prefixes
    if not prefixes:
        print("   no metadataPrefix -- harvest cannot be addressed; stopping.")
        json.dump(out, open(os.path.join(OUTDIR, "46_E10_oai_harvest.json"),
                            "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return 3

    print("\n[3] ListSets")
    r = oai({"verb": "ListSets"})
    sets = re.findall(r"<setSpec>([^<]+)</setSpec>", r["xml"] or "")
    print("   %d sets" % len(sets))
    for s in sets[:40]:
        print("      %s" % s)
    out["steps"]["sets"] = sets[:400]

    # ---- 2. measure before committing ---------------------------------------
    pref = prefixes[0]
    print("\n[4] ListRecords page 1 (metadataPrefix=%s) -- measure first" % pref)
    r = oai({"verb": "ListRecords", "metadataPrefix": pref})
    n1 = len(re.findall(r"<record[ >]", r["xml"] or ""))
    token = tag(r["xml"] or "", "resumptionToken")
    cc = re.search(r"completeListSize=\"?(\d+)", r["xml"] or "")
    print("   records on page 1: %d | completeListSize=%s"
          % (n1, cc.group(1) if cc else "unreported"))
    print("   resumptionToken: %s" % ("present" if token else "ABSENT (single page)"))
    out["steps"]["page1"] = {"records": n1, "completeListSize": cc.group(1)
                             if cc else None, "has_token": bool(token)}

    # ---- 3. harvest ----------------------------------------------------------
    print("\n[5] harvesting up to %d records / %d pages" % (args.max, args.pages))
    seen, pages, hits, hdr_re = 0, 0, [], re.compile(
        r"<header[^>]*>(.*?)</header>(.*?)(?=<record|</ListRecords)", re.S)
    titles = []
    while True:
        xml = r["xml"] or ""
        for hdr, meta in hdr_re.findall(xml):
            ident = tag(hdr, "identifier") or ""
            title = tag(meta, "title") or ""
            desc = tag(meta, "description") or ""
            subj = "; ".join(re.findall(r"<subject>([^<]*)</subject>", meta))
            seen += 1
            blob = " ".join([title, desc, subj])
            hit = [t for t in TERMS if t.lower() in blob.lower()]
            titles.append({"id": ident, "title": title[:200], "hit": hit})
            if hit:
                hits.append({"id": ident, "title": title[:300],
                             "subjects": subj[:300], "terms": hit})
        pages += 1
        token = tag(xml, "resumptionToken")
        if not token or pages >= args.pages or seen >= args.max:
            print("   stop: token=%s pages=%d seen=%d"
                  % ("yes" if token else "no", pages, seen))
            break
        time.sleep(1.0)
        r = oai({"verb": "ListRecords", "resumptionToken": token})
        if not r["transmitted"]:
            print("   page %d NEVER-SENT %s -- stopping with %d records"
                  % (pages + 1, r["error"], seen))
            break

    print("\n[6] %d records harvested, %d term hits" % (seen, len(hits)))
    for h in hits[:60]:
        print("   %-40s %s  <<%s>>" % (h["id"][-40:], h["title"][:70],
                                       ",".join(h["terms"])))
    out["harvest"] = {"records_seen": seen, "pages": pages, "n_hits": len(hits),
                      "hits": hits, "truncated": bool(token)}
    out["terms"] = TERMS
    with open(os.path.join(OUTDIR, "46_E10_oai_harvest.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTDIR, "46_E10_oai_titles.txt"), "w",
              encoding="utf-8", newline="\n") as fh:
        for t in titles:
            fh.write("%s\t%s\n" % (t["id"], t["title"]))
    print("\nwrote 46_E10_oai_harvest.json and 46_E10_oai_titles.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
