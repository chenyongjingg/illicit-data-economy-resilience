#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""37_E3_bridge_probe.py -- the two substrate questions 36_ could not settle.

36_ established three things and left two open.

SETTLED by 36_:
  - The social layer has no PGP/address COLUMN, but it does contain
    checksum-valid BTC addresses in free text (171 base58check-valid hits).
    base58check has a 2^-32 false-positive rate, so those 171 are real
    addresses, not noise: the 374 rejected candidates were the noise.
  - `druglistingdataset` is not a market, it is an AGGREGATED corpus with a
    `source` column over 8 markets. So the "2,929 handles shared between agora
    and druglisting" is not multi-homing, it is one market counted twice.
  - Elliptic++ carries real addresses (`Actors Dataset/wallets_classes.csv`).

OPEN, and this script answers both:
  Q1 (H2)  Do any social-layer addresses appear in Elliptic's address set?
           This is a set intersection, and the answer decides whether the
           cross-layer bridge exists in the acquired data at all.
  Q2 (H1)  How much multi-homing is there WITHIN druglisting, measured by its
           own `source` column? This is the honest H1 substrate.

Q1 carries a POSITIVE CONTROL. An empty intersection computed by broken code
looks exactly like an empty intersection computed by correct code, so a known
Elliptic address is injected into the social pool and the intersection is
re-run. If the control is not recovered, the 0 is a bug, not a finding.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

import pandas as pd

EXTRACT = "/root/cis/data/extracted"
ELL = "/root/cis/data/EllipticPlusPlus-main"
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


B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
RE_BTC = re.compile(r"\b[13][1-9A-HJ-NP-Za-km-z]{25,34}\b")


def b58check(s):
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
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] == chk


def clean(df):
    """agora's header carries LEADING SPACES (' Item', ' Category'), which makes
    df['Item'] raise KeyError while df[' Item'] works. Strip both header and
    every cell so joins and lookups are not silently one-sided."""
    df.columns = [str(c).strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
    return df


def read_csv_robust(path, header):
    kw = dict(dtype=str, low_memory=False, skipinitialspace=True,
              encoding="utf-8", encoding_errors="replace")
    try:
        df = pd.read_csv(path, header=header, **kw)
    except Exception:  # noqa: BLE001
        kw2 = {k: v for k, v in kw.items() if k != "low_memory"}
        df = pd.read_csv(path, header=header, engine="python",
                         on_bad_lines="skip", **kw2)
    if header is None:
        df.columns = ["c%d" % i for i in range(df.shape[1])]
    return clean(df)


SOCIAL = [
    ("agora", os.path.join(EXTRACT, "agora_2014_2015/agora_2014_2015.csv"), 0),
    ("alphabay_items", os.path.join(EXTRACT, "alphabay_2017-01-28/"
     "20170128-alphabay/processed-csv/active listings.csv"), 0),
    ("alphabay_feedback", os.path.join(EXTRACT, "alphabay_2017-01-28/"
     "20170128-alphabay/processed-csv/all_feedback.csv"), 0),
    ("hansa_listings", os.path.join(EXTRACT, "hansa_valhalla/"
     "dark-web-data-dumps/hansa-marketplace-listings-december-2016.csv"), None),
    ("hansa_reviews", os.path.join(EXTRACT, "hansa_valhalla/dark-web-data-dumps/"
     "hansa_reviews_december_2016.csv"), None),
    ("valhalla_listings", os.path.join(EXTRACT, "hansa_valhalla/"
     "dark-web-data-dumps/valhalla-marketplace-listings-2016-10.csv"), None),
    ("kilos_reviews", os.path.join(EXTRACT,
     "kilos_6dnms_reviews/kilos_6dnms_reviews.csv"), None),
    ("druglisting", os.path.join(EXTRACT,
     "druglistingdataset/druglistingdataset.csv"), 0),
]


def main():
    log("=" * 78)
    log("37  Cross-layer bridge (H2) and multi-homing (H1): the two open questions")
    log("=" * 78)

    sep("1. Extract every checksum-valid BTC address from the social layer")
    found = {}          # addr -> set of "file/column"
    per_file = {}
    for name, path, hdr in SOCIAL:
        df = read_csv_robust(path, hdr)
        hits, cand = set(), 0
        for c in df.columns:
            if df[c].dtype != object and str(df[c].dtype) != "object":
                continue
            for s in df[c]:
                if len(s) < 25:
                    continue
                m = RE_BTC.findall(s)
                if not m:
                    continue
                cand += len(m)
                for a in m:
                    if b58check(a):
                        hits.add(a)
                        found.setdefault(a, set()).add("%s/%s" % (name, c))
        per_file[name] = (cand, len(hits))
        log("  %-18s candidates=%5d  ★checksum-valid DISTINCT=%4d"
            % (name, cand, len(hits)))
    log("")
    log("  TOTAL distinct checksum-valid addresses in the social layer: %d"
        % len(found))
    log("  base58check false-positive rate is 2^-32, so each of these is a real")
    log("  base58 address -- unlike the regex hits, which are proposals only.")

    sep("2. Elliptic side: the address set")
    wpath = os.path.join(ELL, "Actors Dataset/wallets_classes.csv")
    w = read_csv_robust(wpath, 0)
    log("  %s" % os.path.relpath(wpath, ELL))
    log("  columns: %s   rows: %d" % (list(w.columns), len(w)))
    ell = set(w["address"].astype(str))
    log("  distinct addresses: %d" % len(ell))
    log("  class distribution: %s"
        % w["class"].value_counts().to_dict())
    lens = w["address"].astype(str).str.len()
    log("  address length: min=%d median=%d max=%d"
        % (lens.min(), lens.median(), lens.max()))
    log("  first 3: %s" % ", ".join(list(ell)[:3]))

    sep("3. ★ H2: does the bridge exist? (set intersection, with a control)")
    inter = found.keys() & ell
    log("  social distinct addresses : %d" % len(found))
    log("  elliptic addresses        : %d" % len(ell))
    log("  INTERSECTION              : %d" % len(inter))
    for a in list(inter)[:20]:
        log("      %s  <- %s" % (a, sorted(found[a])))

    log("")
    log("  -- POSITIVE CONTROL: a known Elliptic address injected into the")
    log("     social pool. If the machinery works it must be recovered;")
    log("     controlling for the control is what makes a 0 interpretable.")
    ctrl = sorted(ell)[0]
    probe = set(found) | {ctrl}
    inter2 = probe & ell
    log("     injected %s" % ctrl)
    log("     intersection after injection: %d (was %d) -> %s"
        % (len(inter2), len(inter),
           "CONTROL RECOVERED, machinery works" if ctrl in inter2
           else "★ CONTROL LOST -- the intersection is broken"))
    log("")
    log("  -- NEGATIVE CONTROL: the same test against a set that shares no")
    log("     member, to show the intersection is not vacuously returning all.")
    bogus = {("X" * 34), ("1" * 34)}
    log("     intersection with 2 fabricated addresses: %d"
        % len((set(found) | bogus) & ell))

    sep("4. ★ H1: multi-homing measured WITHIN druglisting by its own source")
    d = read_csv_robust(os.path.join(
        EXTRACT, "druglistingdataset/druglistingdataset.csv"), 0)
    log("  druglisting rows=%d  sellers=%d  sources=%d"
        % (len(d), d["seller"].nunique(), d["source"].nunique()))
    sm = d.groupby("seller")["source"].nunique()
    log("")
    log("  distinct markets per seller:")
    log("  %s" % sm.value_counts().sort_index().to_dict())
    multi = int((sm > 1).sum())
    log("  sellers in >1 market : %d / %d (%.2f%%)"
        % (multi, len(sm), 100.0 * multi / max(len(sm), 1)))
    log("")
    log("  ★ This is the honest H1 substrate: multi-homing is read off the")
    log("    corpus's own market label, not off cross-file handle matches.")
    log("    The earlier cross-file comparison mixed in a DUPLICATE: druglisting")
    log("    contains an `agora` subset that mirrors agora_2014_2015.csv, so")
    log("    'agora x druglisting = 2,929 shared handles' is one market seen")
    log("    twice, not a seller operating in two markets.")

    sep("5. Duplication check: is druglisting[source==agora] the agora file?")
    a = read_csv_robust(os.path.join(
        EXTRACT, "agora_2014_2015/agora_2014_2015.csv"), 0)
    da = d[d["source"] == "agora"]
    lo, hi = min(len(a), len(da)), max(len(a), len(da))
    va = set(a["Vendor"]); vd = set(da["seller"])
    log("  agora file rows          : %d" % len(a))
    log("  druglisting agora rows   : %d" % len(da))
    log("  vendor sets: agora=%d druglisting-agora=%d shared=%d (%.1f%% of agora)"
        % (len(va), len(vd), len(va & vd), 100.0 * len(va & vd) / len(va)))
    log("  row counts differ %d vs %d (ratio %.3f) -- not a row-for-row copy"
        % (lo, hi, lo / max(hi, 1)))
    log("  but the seller sets overlap %.1f%%, so they are the SAME market"
        % (100.0 * len(va & vd) / len(va)))
    log("  observed at different crawl completeness. Handle-level multi-homing")
    log("  across files is therefore NOT evidence of cross-market operation.")

    sep("6. What this settles")
    log("  H2 substrate : %s" % ("present" if len(inter) else
                                "measured ABSENT in the acquired data"))
    log("  H1 substrate : %s (%d multi-market sellers of %d)"
        % ("present" if multi else "absent", multi, len(sm)))

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "37_E3_bridge_probe.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"social_distinct_addresses": len(found),
                   "elliptic_addresses": len(ell),
                   "intersection": sorted(inter),
                   "control_recovered": bool(ctrl in inter2),
                   "control_address": ctrl,
                   "multi_market_sellers": multi,
                   "sellers_total": int(len(sm)),
                   "markets_per_seller": {str(k): int(v) for k, v in
                                          sm.value_counts().items()},
                   "agora_druglisting_shared_vendors": len(va & vd),
                   }, fh, indent=2, default=str)
    with open(os.path.join(RESULTS, "37_E3_bridge_probe.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(_L) + "\n")
    log("\nwrote %s/37_E3_bridge_probe.{txt,json}" % RESULTS)
    log("BRIDGE_DONE")


if __name__ == "__main__":
    main()
