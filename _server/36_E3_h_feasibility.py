#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""36_E3_h_feasibility.py -- does E3's pre-registered design have data under it?

E3 is specified as "PSM + DiD (H1-H4) + 500 placebo tests" with
    H1 decentralization      -> recovery time down
    H2 cross-layer bridging  -> recovery time down
    H3 functional redundancy -> function recovery up
    H4 raw centrality        -> no significant positive relation to resilience

Before running any of that, each hypothesis needs its measurement substrate to
be shown to EXIST. This is the same discipline the last stage forced on the
last experiment: 29_ asked what `url_status` actually meant before designing on
it, and the answer changed the design. Here the question is whether the four
moderators are measurable in the acquired data at all.

The load-bearing test is H2. The plan's bridging key is
    "PGP / 收款地址 <-> Elliptic 链上地址 (rule matching first)"
which requires PGP keys or payment addresses in the social layer, and Elliptic
addresses on the other side. The social files have no such COLUMN (checked:
headers are Vendor/Category/Item/... and date/time/comment/rating/item), but an
absent column does not prove an absent key -- an address can sit inside a free
text description.

So the scan does not ask "is this string address-shaped". A regex that matches
address-shaped strings is a substring test, and a substring test against free
text gives false positives (C-57). It asks whether the matched string DECODES
as a base58check address, which random alphanumeric noise does not do. The
regex proposes candidates; the checksum disposes.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re

import numpy as np
import pandas as pd

EXTRACT = "/root/cis/data/extracted"
ELLIPTIC = "/root/cis/data/EllipticPlusPlus-main"
RESULTS = "/root/cis/results"
_L: list[str] = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _L.append(s)


def sep(t):
    log("")
    log("=" * 78)
    log(t)
    log("=" * 78)


# ---------------------------------------------------------------- base58check
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58check(s):
    """True iff s decodes as valid base58check (a real BTC legacy address)."""
    n = 0
    for ch in s:
        i = B58.find(ch)
        if i < 0:
            return False
        n = n * 58 + i
    nz = len(s) - len(s.lstrip("1"))
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    raw = b"\x00" * nz + body
    if len(raw) < 5:
        return False
    payload, chk = raw[:-4], raw[-4:]
    d = hashlib.sha256(hashlib.sha256(payload).digest()).digest()
    return d[:4] == chk


RE_BTC = re.compile(r"\b[13][1-9A-HJ-NP-Za-km-z]{25,34}\b")
RE_BECH = re.compile(r"\bbc1[ac-hj-np-z02-9]{25,62}\b")
RE_ETH = re.compile(r"\b0x[0-9a-fA-F]{40}\b")
RE_XMR = re.compile(r"\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b")
RE_PGP = re.compile(r"BEGIN PGP|PGP PUBLIC KEY BLOCK|PGP SIGNATURE", re.I)

# name -> (path, has_header, vendor-ish column index, category-ish column, note)
FILES = [
    ("agora", os.path.join(EXTRACT, "agora_2014_2015/agora_2014_2015.csv"),
     True, "Vendor", "Category", ""),
    ("alphabay_items",
     os.path.join(EXTRACT, "alphabay_2017-01-28/20170128-alphabay/"
                  "processed-csv/active listings.csv"),
     True, None, None, "header unknown until read"),
    ("alphabay_feedback",
     os.path.join(EXTRACT, "alphabay_2017-01-28/20170128-alphabay/"
                  "processed-csv/all_feedback.csv"),
     True, None, None, "no seller column in header"),
    ("hansa_listings",
     os.path.join(EXTRACT, "hansa_valhalla/dark-web-data-dumps/"
                  "hansa-marketplace-listings-december-2016.csv"),
     False, 3, 5, "no header row; positional"),
    ("hansa_reviews",
     os.path.join(EXTRACT, "hansa_valhalla/dark-web-data-dumps/"
                  "hansa_reviews_december_2016.csv"),
     False, 5, None, "no header row; positional"),
    ("valhalla_listings",
     os.path.join(EXTRACT, "hansa_valhalla/dark-web-data-dumps/"
                  "valhalla-marketplace-listings-2016-10.csv"),
     False, 2, None, "no header row; positional"),
    ("kilos_reviews",
     os.path.join(EXTRACT, "kilos_6dnms_reviews/kilos_6dnms_reviews.csv"),
     False, 0, None, "no header row; positional"),
    ("druglisting",
     os.path.join(EXTRACT, "druglistingdataset/druglistingdataset.csv"),
     True, "seller", None, ""),
]


def raw_line_count(path):
    n = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for _ in fh:
            n += 1
    return n


def read_any(path, has_header):
    """Read, and if the C parser chokes on ragged rows fall back to the python
    engine while COUNTING the lines lost. A silent drop would understate the
    text available for the address scan and inflate every 'no address' claim."""
    kw = dict(dtype=str, low_memory=False, skipinitialspace=True,
              encoding="utf-8", encoding_errors="replace")
    hdr = 0 if has_header else None
    try:
        df = pd.read_csv(path, header=hdr, **kw)
        lost = 0
    except Exception:  # noqa: BLE001
        kw2 = {k: v for k, v in kw.items() if k != "low_memory"}
        try:
            df = pd.read_csv(path, header=hdr, engine="python",
                             on_bad_lines="skip", **kw2)
        except Exception:  # noqa: BLE001
            df = pd.read_csv(path, header=hdr, engine="python",
                             on_bad_lines="skip", sep=None, **kw2)
        expect = raw_line_count(path) - (1 if has_header else 0)
        lost = max(expect - len(df), 0)
    if not has_header:
        df.columns = ["c%d" % i for i in range(df.shape[1])]
    df.attrs["lost_lines"] = lost
    return df


def main():
    log("=" * 78)
    log("36  E3 hypothesis feasibility -- does the substrate exist?")
    log("=" * 78)

    frames = {}
    sep("1. File inventory")
    log("  %-18s %9s %5s %-7s %s" % ("file", "rows", "cols", "header", "cols"))
    for name, path, hdr, vend, cat, note in FILES:
        if not os.path.exists(path):
            log("  %-18s  MISSING  %s" % (name, path))
            continue
        df = read_any(path, hdr)
        frames[name] = df
        cols = list(df.columns)
        log("  %-18s %9d %5d %-7s %s"
            % (name, len(df), len(cols), "yes" if hdr else "NO",
               ",".join(str(c)[:14] for c in cols[:9])))
        if len(cols) > 9:
            log("        ALL COLS: %s"
                % " | ".join(str(c) for c in cols))
        if df.attrs.get("lost_lines"):
            log("        ★ %d lines unparseable and SKIPPED"
                % df.attrs["lost_lines"])
        if note:
            log("        note: %s" % note)
        if not hdr:
            log("        row0: %s" % " | ".join(
                str(v)[:26] for v in df.iloc[0].tolist()[:7]))

    sep("2. Coverage: which column is a usable timestamp?")
    log("  A panel needs time. For each column, the share of a 20k sample")
    log("  that parses as a datetime; >=50%% is reported.")
    for name, df in frames.items():
        s = df.head(20000)
        best = []
        for c in df.columns:
            v = pd.to_datetime(s[c].astype(str).str.strip(), errors="coerce",
                               format="mixed")
            frac = float(v.notna().mean()) if len(v) else 0.0
            if frac >= 0.5:
                best.append((c, frac, v.min(), v.max()))
        if not best:
            log("  %-18s  (no timestamp-like column)" % name)
        for c, frac, lo, hi in best[:4]:
            log("  %-18s  %-14s %5.1f%%  %s .. %s"
                % (name, str(c)[:14], 100 * frac, str(lo)[:10], str(hi)[:10]))

    sep("3. H3 substrate: a category / function column?")
    log("  H3 (functional redundancy) needs a function label to be redundant in.")
    for name, path, hdr, vend, cat, note in FILES:
        if name not in frames:
            continue
        df = frames[name]
        cand = [c for c in df.columns
                if re.search(r"categ|type|class|func|item|product|title",
                             str(c), re.I)]
        if cat is not None:
            cand.append(cat)
        if not cand:
            log("  %-18s  NO category-like column" % name)
            continue
        for c in dict.fromkeys(cand):
            if c not in df.columns:
                continue
            nun = df[c].nunique(dropna=True)
            log("  %-18s  %-16s %6d distinct   e.g. %s"
                % (name, str(c)[:16], nun,
                   "; ".join(str(x)[:22] for x in
                             df[c].dropna().astype(str).unique()[:3])))

    sep("4. H1/H4 substrate: do vendor handles repeat ACROSS markets?")
    log("  H1 (decentralization) needs a vendor present in >1 market;")
    log("  H4 (centrality) needs the seller-market bipartite graph. Both need a")
    log("  handle that can be matched across files. Matching is exact-string")
    log("  only: no normalisation is applied and none is claimed.")
    hs = {}
    for name, path, hdr, vend, cat, note in FILES:
        if name not in frames or vend is None:
            continue
        df = frames[name]
        col = vend if isinstance(vend, str) else "c%d" % vend
        if col not in df.columns:
            log("  %-18s  vendor column %r not found" % (name, col))
            continue
        v = df[col].dropna().astype(str).str.strip()
        v = v[(v != "") & (v.str.len() <= 40) & (~v.str.contains(r"^---"))]
        hs[name] = set(v.unique())
        log("  %-18s  %-8s %7d distinct handles" % (name, col, len(hs[name])))
    log("")
    names = sorted(hs)
    log("  pairwise intersection of handle sets:")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = hs[names[i]], hs[names[j]]
            inter = a & b
            log("    %-18s x %-18s  %5d shared   (of %d and %d)"
                % (names[i], names[j], len(inter), len(a), len(b)))
    allh = {}
    for n in names:
        for h in hs[n]:
            allh.setdefault(h, set()).add(n)
    multi = {h: m for h, m in allh.items() if len(m) > 1}
    log("")
    log("  ★ handles appearing in >1 market: %d of %d (%.2f%%)"
        % (len(multi), len(allh), 100.0 * len(multi) / max(len(allh), 1)))
    for h, m in list(multi.items())[:12]:
        log("      %-24s %s" % (h[:24], sorted(m)))

    sep("5. ★ H2 substrate: any PGP key or payment address? (checksum-verified)")
    log("  A regex hit is a candidate, not a finding. For BTC legacy addresses")
    log("  the base58check checksum is recomputed; only a valid checksum counts")
    log("  as a REAL address. Noise in free text cannot pass that test.")
    log("")
    log("  %-18s %9s %9s %9s %9s %9s %9s"
        % ("file", "btc_cand", "btc_VALID", "bech32", "eth", "xmr", "pgp"))
    tot = dict(btc_cand=0, btc_valid=0, bech=0, eth=0, xmr=0, pgp=0)
    examples = []
    for name, df in frames.items():
        blob = {}
        rowcount = {}
        for c in df.columns:
            idx = df[c].dropna().astype(str)
            idx = idx[idx.str.len() >= 20]
            if len(idx) == 0:
                continue
            blob[c] = idx
        bc = bv = be = et = xm = pg = 0
        for c, col in blob.items():
            for s in col:
                m = RE_BTC.findall(s)
                if m:
                    bc += len(m)
                    for cand in m:
                        if b58check(cand):
                            bv += 1
                            if len(examples) < 10:
                                examples.append((name, str(c), cand))
                be += len(RE_BECH.findall(s))
                et += len(RE_ETH.findall(s))
                xm += len(RE_XMR.findall(s))
                if RE_PGP.search(s):
                    pg += 1
        log("  %-18s %9d %9d %9d %9d %9d %9d"
            % (name, bc, bv, be, et, xm, pg))
        tot["btc_cand"] += bc
        tot["btc_valid"] += bv
        tot["bech"] += be
        tot["eth"] += et
        tot["xmr"] += xm
        tot["pgp"] += pg
    log("")
    log("  TOTALS  btc_candidates=%d  ★btc_checksum_valid=%d  bech32=%d  "
        "eth=%d  xmr=%d  pgp=%d"
        % (tot["btc_cand"], tot["btc_valid"], tot["bech"], tot["eth"],
           tot["xmr"], tot["pgp"]))
    if examples:
        log("  checksum-valid examples:")
        for n, c, s in examples:
            log("      %-18s %-14s %s" % (n, c[:14], s))
    else:
        log("  (no checksum-valid BTC legacy address anywhere in the social layer)")

    sep("6. The other side of the bridge: Elliptic address format")
    for p in sorted(glob.glob(os.path.join(ELLIPTIC, "**", "*"), recursive=True)):
        if os.path.isdir(p):
            continue
        sz = os.path.getsize(p)
        log("  %-58s %10d B" % (os.path.relpath(p, ELLIPTIC), sz))
    log("")
    for p in sorted(glob.glob(os.path.join(ELLIPTIC, "**", "*.csv"),
                              recursive=True))[:4]:
        try:
            d = pd.read_csv(p, nrows=3, dtype=str, low_memory=False,
                            encoding="utf-8", encoding_errors="replace")
            log("  %s" % os.path.relpath(p, ELLIPTIC))
            log("      cols: %s" % ",".join(str(c)[:16] for c in d.columns[:12]))
            log("      row0: %s" % " | ".join(str(v)[:20]
                                              for v in d.iloc[0].tolist()[:8]))
        except Exception as e:  # noqa: BLE001
            log("  %s -> %r" % (os.path.relpath(p, ELLIPTIC), e))

    sep("7. Verdict per hypothesis")
    log("  Read off the tables above; no hypothesis is asserted here.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "36_E3_h_feasibility.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"totals": tot,
                   "multi_market_handles": len(multi),
                   "all_handles": len(allh),
                   "valid_btc_examples": examples}, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "36_E3_h_feasibility.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/36_E3_h_feasibility.{txt,json}" % RESULTS)
    log("FEAS_DONE")


if __name__ == "__main__":
    main()
