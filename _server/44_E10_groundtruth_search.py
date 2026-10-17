#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""44_E10_groundtruth_search.py -- actually search ScienceDB for E10's ground truth.

WHY THIS EXISTS
    Report 11 records the ScienceDB "电信诈骗案件集（571 起）" role-labelling ground
    truth as "not found", and explicitly grades that claim as WEAK -- "a single
    generic web search did not hit it, which does not establish non-existence".
    The note "未做站内检索" (never searched the site itself) then sat in the record
    for a full round while the item was escalated to the author as a decision.

    That escalation was my error. "I searched the open web and missed" is a fact
    about my search, not about the dataset; turning it into "decide whether to
    replace it" asked the author to make a call that one on-site search would
    have settled either way. This script pays that debt.

WHAT IT DOES
    Queries ScienceDB's own search surface (scidb.cn) for the plan's dataset by
    name, by count, and by concept. Three-state probing throughout: a request
    that never formed returns "error", never "absent", because the difference
    between "the site says no" and "my request was malformed" is the whole point.

OUTPUT
    44_E10_groundtruth_search.json  -- every request, its state, its answers.
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OUT = "/root/cis/data/external/c13_recon/44_E10_groundtruth_search.json"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# Every query the plan's wording suggests. Chinese and English, name/count/concept.
QUERIES = [
    "电信诈骗案件集",
    "电信诈骗 案件 数据集",
    "诈骗案件 角色标注",
    "角色标注 电信诈骗",
    "571 起 电信诈骗",
    "电信诈骗 571",
    "fraud case role annotation",
    "telecom fraud dataset role",
    "网络诈骗 案件集",
    "诈骗 语料 角色",
]

# Candidate search surfaces. ScienceDB has moved its API around; probe several
# rather than assume one, and record which answered (a 404 is an ANSWER, and is
# recorded as such -- it is evidence about the endpoint, not about the dataset).
ENDPOINTS = [
    "https://www.scidb.cn/api/search/dataset?q={q}&page=1&size=20",
    "https://www.scidb.cn/api/dataset/search?q={q}&page=1&size=20",
    "https://www.scidb.cn/api/search?q={q}",
    "https://www.scidb.cn/s/{q}",
    "https://www.scidb.cn/en/s/{q}",
]


def enc(s):
    """Percent-encode a path/search fragment. Round-trips, so pre-escaped input
    is safe -- and a non-ASCII query can no longer raise before the socket opens
    (the failure that dressed itself up as 'the file is not there')."""
    return urllib.parse.quote(urllib.parse.unquote(s), safe="")


def probe(url, timeout=45):
    """HEAD/GET one URL, keeping 'never sent' apart from 'sent and refused'."""
    rec = {"url": url, "transmitted": False, "status": None, "length": None,
           "ctype": None, "body_head": None, "error": None}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            body = r.read(200000)
            rec["transmitted"] = True
            rec["status"] = r.status
            rec["length"] = len(body)
            rec["ctype"] = r.headers.get("Content-Type")
            rec["body_head"] = body[:4000].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        rec["transmitted"] = True          # a real answer, even if it is "no"
        rec["status"] = exc.code
        try:
            rec["body_head"] = exc.read(2000).decode("utf-8", "replace")
        except Exception:                                          # noqa: BLE001
            pass
    except Exception as exc:                                       # noqa: BLE001
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
    return rec


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    result = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "purpose": "on-site ScienceDB search for E10 role-labelling ground truth",
              "requests": [], "endpoints_answered": [], "hits": []}

    # 1. Which search surfaces answer at all? (an endpoint question, not a data question)
    print("[1] probing search endpoints with a control query")
    endpoint_ok = []
    for tpl in ENDPOINTS:
        url = tpl.format(q=enc("电信诈骗"))
        rec = probe(url)
        state = ("ANSWERED %s" % rec["status"] if rec["transmitted"]
                 else "NEVER-SENT %s" % rec["error"])
        print("   %-58s %s" % (tpl[:58], state))
        rec["kind"] = "endpoint"
        result["requests"].append(rec)
        if rec["transmitted"] and rec["status"] == 200:
            endpoint_ok.append(tpl)

    result["endpoints_answered"] = endpoint_ok
    if not endpoint_ok:
        print("\n!! no search endpoint answered -- this is a fact about the "
              "endpoints I guessed, NOT about the dataset.")
        print("   next step is to fetch the site's own search page and read how it "
              "queries, not to conclude anything about the data.")

    # 2. Now run the real queries against whichever surfaces answered.
    print("\n[2] running %d queries" % len(QUERIES))
    for q in QUERIES:
        for tpl in endpoint_ok or ENDPOINTS[:1]:
            url = tpl.format(q=enc(q))
            rec = probe(url)
            rec["query"] = q
            rec["kind"] = "query"
            result["requests"].append(rec)
            if not rec["transmitted"]:
                print("   %-30s NEVER-SENT %s" % (q[:30], rec["error"]))
                continue
            body = rec["body_head"] or ""
            # Look for the plan's own wording and for any total-count field.
            marks = [m for m in ("电信诈骗", "571", "角色", "total", "count",
                                 "dataset") if m in body]
            print("   %-30s %s len=%s marks=%s"
                  % (q[:30], rec["status"], rec["length"], ",".join(marks) or "-"))
            if "571" in body or ("电信诈骗" in body and rec["length"] > 200):
                result["hits"].append({"query": q, "url": url,
                                       "body_head": body[:3000]})

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print("\nwrote %s" % OUT)
    print("endpoints answered: %d/%d | candidate hits: %d"
          % (len(endpoint_ok), len(ENDPOINTS), len(result["hits"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
