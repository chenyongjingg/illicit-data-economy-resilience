#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""06_E0_figure.py -- E0 figure, relabelled after the tag-role correction.

The first E0 figure had a panel titled "By inferred malware family (from tags)"
whose curves were Mozi, Mirai, `none`, `botnetdomain` and `censys`. Only two of
those five are malware families. `censys` is a scanning service that *found* the
URL, `botnetdomain` describes the URL's shape, and `none` is a placeholder. A
figure asserting they are families would have carried that error into the paper,
where it is much harder to dislodge than a line of a report.

So this splits the tags by role and gives the discovery pathway its own panel,
because that is where the strongest raw contrast lives and it is a statement
about measurement, not about malware.

Output: results/figs/E0_infra_takedown.{png,pdf}
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

import numpy as np
import pandas as pd

WORK = "/root/cis/work"
RESULTS = "/root/cis/results"
FIGS = os.path.join(RESULTS, "figs")

FAMILY = {"mozi", "mirai", "gafgyt", "remcosrat", "rat", "connectwise", "emotet",
          "gozi", "qakbot", "icedid", "trickbot", "cobalt", "amadey", "tsunami",
          "shelldownload", "guloader", "xworm", "agenttesla", "hajime", "bashlite"}
PROVENANCE = {"censys", "shodan", "urlscan", "tweetfeed"}
# `none` is NOT included: it is a placeholder meaning "this URL carries no tags",
# not a submitter tool. Classing it as one inflated the tool-submitted group from
# 8,257 to 11,117 and mixed a null marker into a substantive contrast.
SUBMITTER = {"ua-wget", "ua-curl"}
ARCH = {"32-bit", "64-bit", "mips", "mips64", "arm", "arm64", "x86", "sparc", "ppc"}
PAYLOAD = {"elf", "exe", "dll", "sh", "doc", "docx", "zip", "rar", "msi", "jar",
           "powershell", "hta", "iso", "ascii", "apk", "js", "vbs", "php",
           "python", "html", "binary", "xls"}
IPV4 = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
MAXT = 30


def km_curve(dur, ev, max_t=MAXT):
    d = np.asarray(dur, dtype=float)
    e = np.asarray(ev, dtype=bool)
    o = np.argsort(d)
    d, e = d[o], e[o]
    n, at, i, S = len(d), len(d), 0, 1.0
    ts, ss = [0.0], [1.0]
    while i < n:
        t, j = d[i], i
        if t > max_t:
            break
        while j < n and d[j] == t:
            j += 1
        k = int(e[i:j].sum())
        if k:
            S *= (1 - k / at)
            ts.append(float(t))
            ss.append(S)
        at -= (j - i)
        i = j
    return np.asarray(ts), np.asarray(ss)


def build():
    u = pd.read_parquet(os.path.join(WORK, "ioc_urlhaus.parquet"))
    u["added"] = pd.to_datetime(u["date_added"], errors="coerce")
    u["lo"] = pd.to_datetime(u["last_online"], errors="coerce")
    u["online"] = u["url_status"].str.lower().eq("online")
    W0, T_END = u["lo"].min(), u["lo"].max()

    def host_of(x):
        try:
            return (urlsplit(x if "://" in x else "http://" + x).hostname or "").lower()
        except Exception:  # noqa: BLE001
            return ""

    u["host"] = [host_of(x) for x in u["url"].astype(str)]
    u["block"] = [("ip24:" + ".".join(h.split(".")[:3])) if IPV4.match(h)
                  else ("host:" + h) for h in u["host"]]
    c = u[u["added"] >= W0].copy()
    c["t_event"] = (c["lo"] - c["added"]).dt.total_seconds() / 86400.0
    c["t_cens"] = (T_END - c["added"]).dt.total_seconds() / 86400.0
    c = c[c["t_event"].notna() & (c["t_event"] >= 0)].copy()
    c["duration"] = np.where(c["online"].to_numpy(), c["t_cens"].to_numpy(),
                             c["t_event"].to_numpy())
    c["event"] = ~c["online"]
    c["n_block"] = c.groupby("block")["id"].transform("size")
    tags = c["tags"].fillna("").apply(
        lambda x: [p.strip().lower() for p in str(x).split(",") if p.strip()])
    c["tagset"] = tags

    def first_family(L):
        for t in L:
            if t in FAMILY:
                return t
        return "(no family tag)"

    def pathway(L):
        s = set(L)
        if s & PROVENANCE:
            return "scanner-discovered\n(censys/shodan tag)"
        if s & SUBMITTER:
            return "tool-submitted\n(ua-wget/ua-curl tag)"
        return "neither tag"

    def first_arch(L):
        for t in L:
            if t in ARCH:
                return t
        return "(no arch tag)"

    c["family"] = tags.apply(first_family)
    c["pathway"] = tags.apply(pathway)
    c["arch"] = tags.apply(first_arch)
    c["days_in"] = (c["added"] - W0).dt.total_seconds() / 86400.0
    return c, W0, T_END


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    c, W0, T_END = build()
    os.makedirs(FIGS, exist_ok=True)
    fig, ax = plt.subplots(2, 3, figsize=(16, 8.6))

    def step(a, sub, label, color=None):
        t_, s_ = km_curve(sub["duration"], sub["event"])
        a.step(t_, s_, where="post", label=label, color=color)

    # (a) overall
    a = ax[0, 0]
    step(a, c, "all URLs (n=%d, %d events)" % (len(c), int(c["event"].sum())), "k")
    a.axhline(0.5, ls=":", c="grey", lw=1)
    a.annotate("median 1.36 d", xy=(1.36, 0.5), xytext=(7, 0.56), fontsize=8,
               arrowprops=dict(arrowstyle="->", lw=.8))
    a.set_title("(a) Overall: time from listing to takedown")
    a.set_ylabel("S(t) = still online")
    a.legend(fontsize=8)

    # (b) malware family -- only tags classified as family
    a = ax[0, 1]
    for g in c["family"].value_counts().head(5).index:
        sub = c[c["family"] == g]
        if len(sub) > 200:
            step(a, sub, "%s (n=%d)" % (g, len(sub)))
    a.set_title("(b) By malware family tag\n(only family-role tags included)")
    a.legend(fontsize=7)

    # (c) discovery / submission pathway
    a = ax[0, 2]
    for g in c["pathway"].value_counts().index:
        sub = c[c["pathway"] == g]
        step(a, sub, "%s (n=%d)" % (g.replace("\n", " "), len(sub)))
    a.set_title("(c) By discovery pathway\n(a measurement property, not a malware one)")
    a.legend(fontsize=7)

    # (d) architecture
    a = ax[1, 0]
    for g in c["arch"].value_counts().head(5).index:
        sub = c[c["arch"] == g]
        if len(sub) > 200:
            step(a, sub, "%s (n=%d)" % (g, len(sub)))
    a.set_title("(d) By architecture tag")
    a.set_xlabel("days since listed")
    a.set_ylabel("S(t) = still online")
    a.legend(fontsize=7)

    # (e) block size -- descriptive only, and labelled so
    a = ax[1, 1]
    labs = ["1", "2", "3-5", "6-20", "21-100", "100+"]
    c["block_bin"] = pd.cut(c["n_block"], [0, 1, 2, 5, 20, 100, 10 ** 9], labels=labs)
    for g in ["1", "3-5", "21-100", "100+"]:
        sub = c[c["block_bin"].astype(str) == g]
        step(a, sub, "%s URL(s) in /24 or host (n=%d)" % (g, len(sub)))
    a.set_title("(e) By URLs sharing a block\nDESCRIPTIVE ONLY - not robust to\n"
                "clustering by block (see 05_)")
    a.set_xlabel("days since listed")
    a.legend(fontsize=7)

    # (f) 14-day takedown rate by cohort week
    a = ax[1, 2]
    H = 14.0
    el = c[c["t_cens"] >= H].copy()
    el["down14"] = el["event"] & (el["t_event"] <= H)
    el["wk"] = (el["days_in"] // 7).astype(int)
    wk = el.groupby("wk").agg(n=("id", "size"), d=("down14", "sum"))
    wk["rate"] = 100.0 * wk["d"] / wk["n"]
    se = 100 * np.sqrt((wk["rate"] / 100) * (1 - wk["rate"] / 100) / wk["n"])
    a.errorbar(wk.index * 7 + 3.5, wk["rate"], yerr=1.96 * se, fmt="o-", capsize=3)
    a.set_ylim(80, 96)
    a.set_title("(f) Takedown within 14 days by cohort week\n"
                "OR/day=1.0016 [0.9999,1.0034] p=0.070 -> no trend")
    a.set_xlabel("days since window start")
    a.set_ylabel("% down within 14 days")

    for a_ in ax.ravel():
        a_.grid(alpha=.3)
    fig.suptitle("E0 - URLhaus takedown latency, observation window %s..%s (n=%d). "
                 "Durations are lower bounds (last sighting, not takedown)."
                 % (W0.date(), T_END.date(), len(c)), fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.955])
    for ext in ("png", "pdf"):
        fp = os.path.join(FIGS, "E0_infra_takedown.%s" % ext)
        fig.savefig(fp, dpi=155)
        print("wrote %s" % fp)
    plt.close(fig)
    print("E0_FIGURE_DONE")


if __name__ == "__main__":
    main()
