#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""49_E10_getrecord.py -- full OAI record dump for the near-neighbour candidates.

WHY THIS EXISTS
    48 checked `571` on word boundaries **in titles only**, while 46 matched terms
    against title+description+subject. So a record whose `571` lives in the
    description would be scored a hit by 46 and then "cleared" by 48. That is a
    false negative built out of two instruments that measured different fields --
    the same shape as the trap this project keeps hitting.

    `10.57760/sciencedb.j00133.00466` ("Datasets of Risk Analysis of Telecom Fraud
    Incidents") is exactly that risk: it is tagged `571,fraud` and it is the single
    closest thing in the repository to what the plan asked for. Before I report any
    conclusion about C-13, its full metadata gets read.

This dumps EVERY field of each GetRecord response, not a selected subset, so a
field I did not think to look at cannot hide the answer.
"""
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.scidb.cn/oai"
UA = "cis-sprint-oai-harvester/1.0 (+research; contact: local)"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

IDS = [
    "10.57760/sciencedb.j00133.00466",   # Risk Analysis of Telecom Fraud Incidents <-- the one
    "10.57760/sciencedb.psych.00598",    # Eye movement data set of Internet fraud
    "10.57760/sciencedb.30490",          # fraud spatio-temporal
    "10.57760/sciencedb.23769",          # Financial fraud, Chinese listed companies
    "10.57760/sciencedb.39228",          # Open Source Intelligence Graph
    "10.57760/sciencedb.44152",          # Fraud Detection Datasets
    "10.57760/sciencedb.35286",          # Voice Conversion Spoofing
    "10.57760/sciencedb.11316",          # Medical insurance data set
    "10.57760/sciencedb.31800",          # Tampering Features of Fuel Dispenser
]

FIELDS = ["title", "creator", "subject", "description", "publisher", "contributor",
          "date", "type", "format", "identifier", "source", "language",
          "relation", "coverage", "rights", "alternateIdentifier", "relatedIdentifier",
          "resourceType", "size", "version"]


def oai(params, timeout=60, tries=3):
    url = BASE + "?" + urllib.parse.urlencode(params)
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return "HTTPERROR %s %s" % (exc.code, exc.read()[:400])
        except Exception as exc:                                  # noqa: BLE001
            last = "%s: %s" % (type(exc).__name__, exc)
            time.sleep(2 * (a + 1))
    return "NEVER-SENT " + last


def all_tags(xml, name):
    return re.findall(r"<%s[^>]*>(.*?)</%s>" % (name, name), xml, re.S | re.I)


def main():
    out = {}
    for ident in IDS:
        print("=" * 74)
        print(ident)
        print("=" * 74)
        xml = oai({"verb": "GetRecord", "metadataPrefix": "oai_datacite",
                   "identifier": ident})
        if xml.startswith(("NEVER-SENT", "HTTPERROR")):
            print("   %s" % xml[:200])
            out[ident] = {"error": xml[:400]}
            continue
        rec = {}
        for f in FIELDS:
            vals = [re.sub(r"\s+", " ", v).strip() for v in all_tags(xml, f)]
            if vals:
                rec[f] = vals
        if not rec:                       # different element names -> show raw
            print("   no known field matched; raw (first 1500 chars):")
            print("   " + re.sub(r"\s+", " ", xml)[:1500])
            out[ident] = {"raw": xml[:4000]}
            continue
        for f in FIELDS:
            if f not in rec:
                continue
            for v in rec[f][:6]:
                print("   %-18s %s" % (f, v[:400]))
        # explicit: where does a bare 571 appear, and in which field?
        for f, vals in rec.items():
            for v in vals:
                for m in re.finditer(r"571", v):
                    s, e = max(0, m.start() - 25), m.end() + 25
                    nb = "WORD-BOUNDARY" if (
                        (m.start() == 0 or not v[m.start() - 1].isdigit()) and
                        (m.end() >= len(v) or not v[m.end()].isdigit())) else "digit-substring"
                    print("   [571 in %s] %s :: ...%s..." % (f, nb, v[s:e]))
        out[ident] = rec
        time.sleep(1.0)

    json.dump(out, open("/root/cis/data/external/c13_recon/49_E10_getrecord.json",
                        "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\nwrote 49_E10_getrecord.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
