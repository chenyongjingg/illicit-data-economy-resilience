#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""43_E9_anchor_fetch.py -- download + verify the E9 anchor series, in parallel.

Reuses 42's verification logic by importing it, so there is exactly ONE definition
of "we have the file" (bytes == declared Content-Length AND %%EOF within the last
2 KiB). Duplicating that check would recreate the very problem it exists to catch.

WHY PARALLEL: the site serves ~23-28 KB/s per connection but allows several at
once -- a second concurrent connection measured ~28 KB/s while the first ran at
~23 KB/s. Serially that is ~23 min per 32 MB issue (~3.5 h for the set); with a
pool it is wall-clock-bounded by the slowest single connection instead.

WHY THE PROBE WINDOW IS WIDER HERE: 42 probed publication month mo or mo+1 only,
which cannot find a December issue -- a 2025.12 report is published in January
2026, and mo+1 = 13 was discarded. This script rolls the window across the year
boundary.

★ C-209 (2026-09-24). `n_series_extracted`, and every `issues[].effective_items`,
are the **RAW (pre-despacing)** layer. The shipped `results/51_E9_series.json`
carries BOTH layers per report, and its `per_report[*].despaced` is the one that
record itself declares cross-machine comparable. The despaced layer covers MORE
periods than this count (measured 2026-09-24 for 2025: raw hits 3, despaced hits 4
-- 2025-04 is `pattern_found_raw=false / pattern_found_despaced=true`, 509,880).
So reading `n_series_extracted` as "the series has this many periods" UNDERSTATES
it. This revision therefore labels the layer in the payload and in the text twin
instead of leaving the reader to infer it. The artefact published in
`output/cis_sprint_20260924/` (manifest-named) was NOT regenerated and NOT edited:
regenerating it would break that package's own `sha256sum -c` criterion.
"""
import concurrent.futures as cf
import importlib.util
import json
import os
import sys
import urllib.parse

SPEC = importlib.util.spec_from_file_location(
    "e9anchor", "/root/cis/scripts/42_E9_anchor_dwcon.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
RES_JSON = "/root/cis/results/43_E9_anchor_fetch.json"
RES_TXT = "/root/cis/results/43_E9_anchor_fetch.txt"
URLMAP = "/root/cis/results/43_E9_anchor_urls.json"

# Months 42 could not locate. 2025.12 was probed only in month 12; 05 and 09 got
# a full year-window scan and came back answered-absent for every request sent.
RETRY = [5, 9, 12]


def pub_candidates(mo):
    """(pub_year_offset, pub_month) pairs; rolls over the year end."""
    out = []
    for k in (0, 1, 2):
        m = mo + k
        yr = 0
        while m > 12:
            m -= 12
            yr += 1
        out.append((yr, m))
    return out


def probe_month(mo, year=M.YEAR):
    """Wider second pass for one month. Returns (url|None, stats)."""
    mine = "【数世咨询】全球数据泄露态势月度报告（%d.%d）.pdf"
    sent = absent = inconclusive = 0
    for off, pm in pub_candidates(mo):
        for d in sorted({year, year + 1, year + off}):
            for day in range(1, 32):
                mmdd = "%02d%02d" % (pm, day)
                url = "/uploads/file/%d/%s%s" % (d, mmdd, mine % (year, mo))
                p = M.probe(M.BASE + url)
                if not p["transmitted"]:
                    inconclusive += 1
                    continue
                sent += 1
                if p["status"] == 200 and (p["length"] or 0) > 100_000:
                    return url, (sent, absent, inconclusive)
                absent += 1
    return None, (sent, absent, inconclusive)


def main():
    print("[1] discovery + primary probe (reusing 42)")
    found = M.discover()
    found, _ = M.probe_missing(found)

    print("[2] wider second pass for %s" % RETRY)
    stats = {}
    for mo in RETRY:
        if (M.YEAR, mo) in found:
            continue
        url, st = probe_month(mo)
        stats["%d-%02d" % (M.YEAR, mo)] = st
        print("  %d.%02d -> %s (sent=%d absent=%d never-sent=%d)"
              % (M.YEAR, mo, (url[16:34] if url else "NOT FOUND"), st[0], st[1], st[2]))
        if url:
            found[(M.YEAR, mo)] = url

    urls = {"%d-%02d" % k: v for k, v in sorted(found.items()) if k[0] == M.YEAR}
    with open(URLMAP, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(urls, fh, ensure_ascii=False, indent=2)
    print("[3] %d issue URLs resolved; downloading with %d workers"
          % (len(urls), WORKERS))

    def job(item):
        period, path = item
        dest = os.path.join(M.OUTDIR, "dwcon_%s.pdf" % period)
        rec = M.download(M.BASE + path, dest)
        rec["period"] = period
        if rec.get("ok"):
            rec.update(M.extract(dest))
        return rec

    issues = []
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for rec in pool.map(job, sorted(urls.items())):
            issues.append(rec)
            print("  %s ok=%s bytes=%s/%s eff=%s hv=%s %s"
                  % (rec.get("period"), rec.get("ok"), rec.get("bytes"),
                     rec.get("content_length_declared"), rec.get("effective_items"),
                     rec.get("high_value_items"),
                     rec.get("reason") or rec.get("error") or ""))

    ok = [i for i in issues if i.get("ok")]
    series = [i for i in ok if i.get("effective_items") is not None]
    payload = {
        "what": "E9 external anchor -- DWC monthly leak-posture reports",
        "year": M.YEAR,
        "n_issues_resolved": len(issues),
        "n_verified": len(ok),
        "n_series_extracted": len(series),
        # ★ C-209. These three keys exist so a reader cannot take the count above for
        # "the series has this many periods": it counts issues whose **RAW**
        # `effective_items` is not None, which is a LOWER bound on the usable series.
        "layer": "raw (pre-despacing)",
        "n_series_extracted_means": "issues whose RAW `effective_items` is not None -- "
                                    "NOT the number of periods in the series",
        "despaced_layer_lives_in": "results/51_E9_series.json -> per_report[*].despaced",
        "verification": "bytes == declared Content-Length AND %%EOF in last 2KiB",
        "urls": urls,
        "second_pass_stats": stats,
        "issues": issues,
    }
    os.makedirs(os.path.dirname(RES_JSON), exist_ok=True)
    with open(RES_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    lines = ["E9 anchor -- %d  (verified = bytes match declared AND real trailer)" % M.YEAR, ""]
    lines.append("%-8s %-4s %-11s %-12s %-12s %-12s %s"
                 % ("period", "ok", "bytes", "declared", "effective", "high_value", "sha256"))
    for i in sorted(issues, key=lambda r: r.get("period", "")):
        lines.append("%-8s %-4s %-11s %-12s %-12s %-12s %s"
                     % (i.get("period"), i.get("ok"), i.get("bytes"),
                        i.get("content_length_declared"), i.get("effective_items"),
                        i.get("high_value_items"), (i.get("sha256") or "")[:16]))
    lines += ["", "resolved %d | verified %d | RAW-layer series %d  "
              "(despaced layer covers more -- see results/51_E9_series.json)"
              % (len(issues), len(ok), len(series))]
    with open(RES_TXT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if series else 1


if __name__ == "__main__":
    sys.exit(main())
