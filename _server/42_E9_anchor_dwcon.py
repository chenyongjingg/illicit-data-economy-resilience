#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""42_E9_anchor_dwcon.py -- acquire E9's external anchor (DWC monthly leak-posture reports).

Runs ON THE POD. Downloads the series once, server-side, so the author's hotspot
carries only the extracted table (~KBs), not ~380 MB of PDFs.

TWO DEFECTS THIS FILE EXISTS TO NOT REPEAT (C-99)
-------------------------------------------------
(a) "Downloaded" is not "have the file". The first download of issue 2025.3 was
    recorded as 9,158,656 B with a sha256 -- both were properties of MY transfer,
    not of the report (real size 31,921,548 B, i.e. 28.7%). The transfer had been
    cut by `--max-time`; `size_download` is "how much arrived before I killed it".
    A 200 with the right magic bytes can still be a prefix, and PyMuPDF repaired
    the prefix silently, so nothing downstream complained. Hence: every file must
    match the declared Content-Length AND carry a real trailer.

(b) "Not found" is not "absent". The first probing run printed
    "no URL found (124 HEADs, all negative)" for eleven months. Not one of those
    HEADs was ever sent: the target filenames contain full-width characters and
    http.client cannot encode them, so urllib raised UnicodeEncodeError before
    opening a socket -- and a bare `except Exception: return None` folded
    "the server said no" together with "my request was malformed". The caller then
    reported my code's failure as the world's answer.
    Hence: probe() separates TRANSMITTED from ABSENT, and absence claims are
    only made about requests that actually went out and came back.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.dwcon.cn"
OUTDIR = "/root/cis/data/external/dwcon"
RES_JSON = "/root/cis/results/42_E9_anchor_dwcon.json"
RES_TXT = "/root/cis/results/42_E9_anchor_dwcon.txt"
YEAR = 2025
UA = {"User-Agent": "Mozilla/5.0 (compatible; research-data-acquisition)"}

PAT_EFFECTIVE = re.compile(r"深网和暗网有效情报\s*([\d,]+)\s*份")
PAT_HIGHVALUE = re.compile(r"泄露数据的高价值买卖情报\s*([\d,]+)\s*份")
PAT_MONTH = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月共监控到全球")
# Matches the report filename, whether the link is raw or percent-encoded.
PAT_PDF = re.compile(r"/uploads/file/\d{4}/[^\"'\s<>]*?全球数据泄露态势月度报告（(\d{4})\.(\d{1,2})）\.pdf")


def enc(path):
    """Percent-encode a URL path. Round-trips, so already-escaped input is safe.

    Unquote first: some hrefs are already encoded, and quoting those again would
    turn %E3 into %25E3 -- a different, nonexistent file.
    """
    return urllib.parse.quote(urllib.parse.unquote(path), safe="/")


def eu(url):
    """Encode only the path of an absolute URL, leaving scheme and host alone.

    Every request goes through here. Without it, a target filename containing
    full-width characters raises UnicodeEncodeError inside http.client before a
    socket is opened -- and that failure looks exactly like a 404.
    """
    s = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((s.scheme, s.netloc, enc(s.path), s.query, s.fragment))


def fetch(url, timeout=90):
    """GET, returning (bytes, error). Non-ASCII paths are encoded, not assumed."""
    try:
        req = urllib.request.Request(eu(url), headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), None
    except Exception as exc:                                    # noqa: BLE001
        return None, "%s: %s" % (type(exc).__name__, exc)


def probe(url, timeout=45):
    """HEAD one candidate. Separates TRANSMITTED-but-absent from NEVER-SENT.

    Returns {"transmitted": bool, "status": int|None, "length": int|None,
             "error": str|None}. `transmitted=False` means the request never
    reached the network and says NOTHING about whether the file exists.
    """
    out = {"transmitted": False, "status": None, "length": None, "error": None}
    try:
        req = urllib.request.Request(eu(url), headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out["transmitted"] = True
            out["status"] = r.status
            cl = r.headers.get("Content-Length")
            out["length"] = int(cl) if cl else None
    except urllib.error.HTTPError as exc:
        # A real answer from the server: the file is not there.
        out["transmitted"] = True
        out["status"] = exc.code
    except Exception as exc:                                    # noqa: BLE001
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
    return out


def download(url, dest):
    """Download with verification. `ok` requires length match AND a real trailer."""
    rec = {"url": url, "path": dest, "ok": False}
    declared = probe(url)
    rec["content_length_declared"] = declared["length"]
    rec["head_transmitted"] = declared["transmitted"]
    if not declared["transmitted"]:
        rec["error"] = "HEAD never sent: %s" % declared["error"]
        return rec
    try:
        req = urllib.request.Request(eu(url), headers=UA)
        with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as fh:
            h = hashlib.sha256()
            n = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                h.update(chunk)
                n += len(chunk)
        rec["bytes"] = n
        rec["sha256"] = h.hexdigest()
        with open(dest, "rb") as fh:
            fh.seek(max(0, n - 2048))
            tail = fh.read()
        rec["has_eof"] = b"%%EOF" in tail
        rec["has_startxref"] = b"startxref" in tail
        rec["ok"] = (
            (rec["content_length_declared"] is None
             or n == rec["content_length_declared"])
            and rec["has_eof"]
            and n > 100_000
        )
        if not rec["ok"]:
            rec["reason"] = ("bytes=%s declared=%s eof=%s"
                             % (n, rec["content_length_declared"], rec["has_eof"]))
    except Exception as exc:                                    # noqa: BLE001
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
    return rec


def read_text(path):
    """Text layer from two independent extractors; both outcomes recorded."""
    out = {}
    try:
        import fitz
        doc = fitz.open(path)
        out["fitz_chars"] = sum(len(p.get_text()) for p in doc)
        out["_text"] = "\n".join(p.get_text() for p in doc)
    except Exception as exc:                                    # noqa: BLE001
        out["fitz_error"] = "%s: %s" % (type(exc).__name__, exc)
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        out["pypdf_chars"] = sum(len(p.extract_text() or "") for p in reader.pages)
    except Exception as exc:                                    # noqa: BLE001
        out["pypdf_error"] = "%s: %s" % (type(exc).__name__, exc)
    return out


def extract(path):
    """The two monthly series values. Never guesses; records both extractors."""
    out = read_text(path)
    text = out.pop("_text", None)
    if not text:
        out["error"] = "no text layer from either extractor"
        return out
    out["text_chars"] = len(text)
    m = PAT_MONTH.search(text)
    out["stated_period"] = ("%s-%02d" % (m.group(1), int(m.group(2)))) if m else None
    for key, pat in (("effective_items", PAT_EFFECTIVE),
                     ("high_value_items", PAT_HIGHVALUE)):
        mm = pat.search(text)
        out[key] = int(mm.group(1).replace(",", "")) if mm else None
    return out


def discover():
    """Monthly-report links found on the site's own article pages."""
    found = {}
    ids = set()
    for page in ("/report", "/report?page=2", "/report?page=3", "/report?page=4"):
        raw, err = fetch(BASE + page)
        if raw is None:
            print("  listing %s FAILED: %s" % (page, err))
            continue
        ids |= set(re.findall(r'href="/post/(\d+)"', raw.decode("utf-8", "replace")))
    print("  listing gave %d candidate posts" % len(ids))
    sent = 0
    for pid in sorted(ids, key=int):
        raw, err = fetch("%s/post/%s" % (BASE, pid))
        if raw is None:
            continue
        sent += 1
        # Unquote before matching: a link may be percent-encoded in the HTML.
        html = urllib.parse.unquote(raw.decode("utf-8", "replace"))
        for m in PAT_PDF.finditer(html):
            found.setdefault((int(m.group(1)), int(m.group(2))), m.group(0))
        time.sleep(0.1)
    print("  %d posts fetched, %d issue links" % (sent, len(found)))
    return found


def probe_missing(found):
    """Probe publication-date prefixes for months with no link on the site.

    Reports TRANSMITTED counts, so "not found" is only ever said about requests
    that were actually sent and answered.
    """
    mine = "【数世咨询】全球数据泄露态势月度报告（%d.%d）.pdf"
    stats = {}
    for mo in range(1, 13):
        if (YEAR, mo) in found:
            continue
        sent = absent = inconclusive = 0
        hit = None
        for pub_month in (mo + 1, mo):
            if not 1 <= pub_month <= 12 or hit:
                continue
            for day in range(1, 32):
                if hit:
                    break
                mmdd = "%02d%02d" % (pub_month, day)
                for d in (YEAR, YEAR + 1):
                    url = "/uploads/file/%d/%s%s" % (d, mmdd, mine % (YEAR, mo))
                    p = probe(BASE + url)
                    if not p["transmitted"]:
                        inconclusive += 1
                        continue
                    sent += 1
                    if p["status"] == 200 and (p["length"] or 0) > 100_000:
                        hit = url
                        break
                    absent += 1
        if hit:
            found[(YEAR, mo)] = hit
            print("  %d.%02d HIT %s (sent=%d absent=%d never-sent=%d)"
                  % (YEAR, mo, hit[16:34], sent, absent, inconclusive))
        else:
            stats["%d-%02d" % (YEAR, mo)] = (sent, absent, inconclusive)
            print("  %d.%02d no match (sent=%d answered-absent=%d never-sent=%d)"
                  % (YEAR, mo, sent, absent, inconclusive))
    return found, stats


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    os.makedirs(os.path.dirname(RES_JSON), exist_ok=True)

    print("[1] discovering issue links")
    found = discover()
    print("[2] probing months with no link on site")
    found, stats = probe_missing(found)

    issues = []
    for (y, mo) in sorted(found):
        if y != YEAR:
            continue
        url = found[(y, mo)]
        dest = os.path.join(OUTDIR, "dwcon_%d-%02d.pdf" % (y, mo))
        print("[3] %d.%02d %s" % (y, mo, url[:74]))
        rec = download(BASE + url, dest)
        rec["period"] = "%d-%02d" % (y, mo)
        if rec.get("ok"):
            rec.update(extract(dest))
        issues.append(rec)
        print("      ok=%s bytes=%s/%s eff=%s hv=%s %s"
              % (rec.get("ok"), rec.get("bytes"), rec.get("content_length_declared"),
                 rec.get("effective_items"), rec.get("high_value_items"),
                 rec.get("reason") or rec.get("error") or ""))

    ok = [i for i in issues if i.get("ok")]
    series = [i for i in ok if i.get("effective_items") is not None]
    payload = {
        "what": "E9 external anchor -- DWC (数世咨询) x 零零信安 monthly leak-posture reports",
        "year": YEAR,
        "n_issues_found": len(issues),
        "n_verified": len(ok),
        "n_series_extracted": len(series),
        "verification": "ok requires: bytes == declared Content-Length "
                        "AND %%EOF within last 2KiB AND >100000 bytes",
        "probe_stats_never_sent": stats,
        "issues": issues,
    }
    with open(RES_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    lines = ["E9 anchor acquisition -- %d" % YEAR, ""]
    lines.append("%-8s %-5s %-11s %-12s %-13s %-12s %s"
                 % ("period", "ok", "bytes", "declared", "effective", "high_value", "sha256"))
    for i in sorted(issues, key=lambda r: r.get("period", "")):
        lines.append("%-8s %-5s %-11s %-12s %-13s %-12s %s"
                     % (i.get("period"), i.get("ok"), i.get("bytes"),
                        i.get("content_length_declared"), i.get("effective_items"),
                        i.get("high_value_items"), (i.get("sha256") or "")[:16]))
    lines.append("")
    lines.append("issues found: %d | verified: %d | series extracted: %d"
                 % (len(issues), len(ok), len(series)))
    with open(RES_TXT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    print("\n".join(lines))
    return 0 if series else 1


if __name__ == "__main__":
    sys.exit(main())
