#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_escaped_cr.py -- repair the ledger text I clobbered with a heredoc.

What happened: C-93's ledger entry was appended through a quoted bash heredoc,
and this machine eats one level of backslashes in a heredoc (a defect already
recorded as G-67 in the cross-project ledger: "含反斜杠的判据一律写 .py 再跑").
So the escape sequences I meant to write as literal TEXT were taken as literal
BYTES: every place I wrote the two characters backslash-r came out as a real
carriage return (0x0d).

Effect: 6 CR bytes inside code spans in pipeline_reports/progress.md, which is
the same class of defect as C-93 itself -- a record whose bytes are not what
its text claims. Repair by mapping each 0x0d back to the two characters it was
supposed to be. Restricted to the C-93 section so nothing earlier is touched.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "pipeline_reports", "progress.md")
MARK = "### ★ C-93".encode("utf-8")
CR = b"\x0d"
ESC = b"\\" + b"r"          # the two characters backslash, r


def main():
    with open(LEDGER, "rb") as fh:
        raw = fh.read()
    i = raw.find(MARK)
    if i < 0:
        print("C-93 section not found; nothing to do")
        return 1
    head, tail = raw[:i], raw[i:]
    n = tail.count(CR)
    if n == 0:
        print("no stray CR in the C-93 section; nothing to do")
        return 0
    fixed = tail.replace(CR, ESC)
    with open(LEDGER, "wb") as fh:
        fh.write(head + fixed)
    with open(LEDGER, "rb") as fh:
        chk = fh.read()
    print("replaced %d stray CR byte(s) with the literal text backslash-r" % n)
    print("file now %d bytes, CR=%d, LF=%d"
          % (len(chk), chk.count(b"\r"), chk.count(b"\n")))
    # show the repaired spans so the repair is visible, not asserted
    for ln in fixed.split(b"\n"):
        if ESC in ln and b"FAILED open" in ln or b"CR" in ln and ESC in ln:
            print("  %s" % ln.decode("utf-8")[:100])
    return 0 if chk.count(b"\r") == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
