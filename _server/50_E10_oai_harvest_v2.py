#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""50_E10_oai_harvest_v2.py -- re-harvest, storing FULL metadata, and re-scan.

WHY THIS REPLACES 46's SCAN
    46 scored terms against `tag(meta, "title") + tag(meta, "description") +
    tag(meta, "subject")`, where `tag()` is

        re.search(r"<name[^>]*>(.*?)</name>", xml, re.S)   -> FIRST match only

    But Datacite records repeat every field: `<title>` (EN and ZH), `<creator>` xN,
    `<subject>` xN, `<description>` xN. Taking the first match means **the Chinese
    abstract is never read** when an English abstract precedes it.

    That is exactly what happened. Record 10.57760/sciencedb.j00133.00466 reads

        description[0] = "The dataset contains 571 telecom fraud cases, ..."
        description[1] = "数据集包含 571 条电信诈骗案例, ..."

    so `571` scored (from the English) and `电信诈骗` scored 0 (the Chinese was
    never seen). The result was a confident "the plan's dataset does not exist"
    built out of a bug in my own extraction -- and 48 then "confirmed" it by
    checking word boundaries in titles only, a different field again.

    Two instruments, one blind spot. Their agreement carried no information.

WHAT THIS DOES INSTEAD
    * reads EVERY instance of EVERY field
    * scans the union of all field text
    * keeps the full record, so any future question can be re-asked without
      re-harvesting 550 pages
    * prints per page, so a 22-minute run is not a black box
"""
import argparse
import collections
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

FIELDS = ["title", "creator", "subject", "description", "publisher", "contributor",
          "date", "type", "format", "identifier", "source", "language",
          "relation", "coverage", "rights", "alternateIdentifier",
          "relatedIdentifier", "resourceType", "size", "version"]

# The plan's E10/C-13 target is a Chinese telecom-fraud case corpus. Search both
# languages, because the deciding text may exist in only one of them.
TERMS = ["电信诈骗", "网络诈骗", "诈骗", "角色标注", "标注", "黑产", "灰产",
         "telecom fraud", "fraud", "scam", "annotation", "labelled", "labeled"]


def oai(params, timeout=60, tries=3):
    url = BASE + "?" + urllib.parse.urlencode(params)
    last = None
    for a in range(tries):
        rec = {"url": url, "transmitted": False, "status": None,
               "error": None, "xml": None}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                rec.update(transmitted=True, status=r.status,
                           xml=r.read().decode("utf-8", "replace"))
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


def strip(s):
    if s is None:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fields_of(block):
    """EVERY instance of EVERY field -- not the first match."""
    out = {}
    for f in FIELDS:
        vals = [strip(v) for v in
                re.findall(r"<%s[^>]*>(.*?)</%s>" % (f, f), block, re.S | re.I)]
        vals = [v for v in vals if v]
        if vals:
            out[f] = vals
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=600)
    ap.add_argument("--max", type=int, default=30000)
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)

    jsonl = os.path.join(OUTDIR, "50_E10_records_full.jsonl")
    r = oai({"verb": "ListRecords", "metadataPrefix": "oai_datacite"})
    if not r["transmitted"]:
        print("NEVER-SENT %s -- transport failure, not an empty repository"
              % r["error"])
        return 2

    seen = pages = 0
    hits = []
    termcount = collections.Counter()
    with open(jsonl, "w", encoding="utf-8", newline="\n") as fh:
        while True:
            xml = r["xml"] or ""
            blocks = re.findall(r"<record[ >].*?</record>", xml, re.S)
            for b in blocks:
                ident = (re.search(r"<identifier>([^<]+)</identifier>", b) or
                         [None, ""])[1] if "<identifier>" in b else ""
                fl = fields_of(b)
                seen += 1
                rec = {"id": ident, "fields": fl}
                blob = " ".join(" ".join(v) for v in fl.values())
                rec["terms"] = [t for t in TERMS if t.lower() in blob.lower()]
                for t in rec["terms"]:
                    termcount[t] += 1
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if rec["terms"]:
                    hits.append({"id": ident,
                                 "title": (fl.get("title") or [""])[0][:200],
                                 "terms": rec["terms"],
                                 "n_fields": len(fl)})
            pages += 1
            token = re.search(r"<resumptionToken[^>]*>(.*?)</resumptionToken>",
                              xml, re.S)
            token = token.group(1).strip() if token else None
            print("   page %3d  seen %6d  hits %3d" % (pages, seen, len(hits)),
                  flush=True)
            if not token or pages >= args.pages or seen >= args.max:
                break
            time.sleep(1.0)
            r = oai({"verb": "ListRecords", "resumptionToken": token})
            if not r["transmitted"]:
                print("   page %d NEVER-SENT %s -- stopping" % (pages + 1, r["error"]))
                break

    print("\n=== %d records / %d pages ===" % (seen, pages))
    for t in TERMS:
        print("   %-16s %d" % (t, termcount[t]))
    summary = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "records_seen": seen, "pages": pages,
               "term_counts": dict(termcount),
               "n_hits": len(hits), "hits": hits,
               "jsonl": jsonl, "terms": TERMS}
    with open(os.path.join(OUTDIR, "50_E10_harvest_v2.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print("wrote 50_E10_harvest_v2.json + %s" % jsonl)
    return 0


if __name__ == "__main__":
    sys.exit(main())
