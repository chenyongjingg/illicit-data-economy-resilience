#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""48_E10_harvest_audit.py -- is the harvest's zero a fact about the HOLDINGS,
or a fact about my term list?

46 harvested 27,500 records (550 pages, truncated=False) and found
  电信诈骗 = 0, 诈骗 = 0, 网络诈骗 = 0, 角色标注 = 0

That number is only a finding about ScienceDB if the harvested metadata actually
carries Chinese text. If the OAI feed is English-only (or romanised), then a
zero on a Chinese term measures the feed's language, not the repository's
contents -- and I would be quoting my own blind spot as their absence.

This is the discipline this project keeps meeting: two instruments agreeing is
not corroboration when they share a blind spot. Here the "instrument" is my
term list and the "object" is the metadata language. So: measure the language of
the object FIRST, then read the term counts.

Also: `571` as a bare substring matches numbers (1571, 5714...). Re-check it on
word boundaries, and print every 571 hit so the reader can judge.
"""
import json
import re
import sys

P = "/root/cis/data/external/c13_recon/46_E10_oai_harvest.json"
T = "/root/cis/data/external/c13_recon/46_E10_oai_titles.txt"

# CJK Unified Ideographs + extension A. If the feed is English-only this is 0.
CJK = re.compile(r"[㐀-䶿一-鿿]")


def main():
    d = json.load(open(P, encoding="utf-8"))
    h = d["harvest"]

    print("=" * 72)
    print("PART 1 -- what language is the object?")
    print("=" * 72)
    rows = []
    with open(T, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t", 1)
            if len(parts) == 2:
                rows.append(parts)
    n = len(rows)
    with_cjk = [r for r in rows if CJK.search(r[1])]
    print("titles in file        : %d" % n)
    print("titles containing CJK : %d  (%.2f%%)" % (len(with_cjk), 100.0 * len(with_cjk) / max(n, 1)))
    print()
    if with_cjk:
        print("sample CJK titles (first 8):")
        for i, t in with_cjk[:8]:
            print("   %-38s %s" % (i[-38:], t[:60]))
    print()

    # Do the CJK titles get *harvested* at all -- i.e. is the loss at the term
    # list or upstream? Print any CJK title containing a fraud-ish character.
    fraudish = [r for r in with_cjk
                if any(c in r[1] for c in "诈骗骗黑灰产敲诈欺")]
    print("CJK titles containing any of 诈骗黑灰产欺 : %d" % len(fraudish))
    for i, t in fraudish[:20]:
        print("   %-38s %s" % (i[-38:], t[:70]))

    print()
    print("=" * 72)
    print("PART 2 -- the 571 hits: real, or digit substrings?")
    print("=" * 72)
    hits571 = [x for x in h["hits"] if "571" in x["terms"]]
    print("hits tagged 571 : %d" % len(hits571))
    strict = 0
    for x in hits571:
        t = x["title"]
        # word-boundary: 571 not preceded/followed by another digit
        if re.search(r"(?<!\d)571(?!\d)", t):
            strict += 1
            print("   WORD-BOUNDARY  %-38s %s" % (x["id"][-38:], t[:60]))
    print("   ...of which on a word boundary (not part of a longer number): %d" % strict)

    print()
    print("=" * 72)
    print("PART 3 -- all 38 hits, deduplicated by id")
    print("=" * 72)
    seen = set()
    for x in h["hits"]:
        if x["id"] in seen:
            continue
        seen.add(x["id"])
        print("   %-40s <<%s>>  %s" % (x["id"][-40:], ",".join(x["terms"]), x["title"][:60]))
    print("   distinct ids: %d" % len(seen))

    print()
    print("=" * 72)
    print("PART 4 -- coverage: did the harvest actually exhaust the repository?")
    print("=" * 72)
    print("records_seen      : %d" % h["records_seen"])
    print("pages             : %d" % h["pages"])
    print("truncated         : %s   (False => resumptionToken ran out)" % h["truncated"])
    print("completeListSize  : %s  (from page 1)" % d["steps"]["page1"]["completeListSize"])
    print("deficit           : %s" % (27503 - h["records_seen"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
