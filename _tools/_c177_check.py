# -*- coding: utf-8 -*-
"""Verify the C-177 landing. My own assertion failed AFTER the write, so the
first question is not "what should the assertion have been" but "what is on
disk now". Two things must be checked before anything else:

1. LINE ENDINGS. `_ledger_c174.py` read binary for `raw`, then text for the
   edit, then wrote text with newline="" -- which converts CRLF -> LF over the
   WHOLE file if the file was CRLF. Its prefix assertion passed both times,
   which is evidence the file is LF, but evidence-by-inference is exactly what
   this project keeps getting wrong. Count the bytes.
2. That the marker landed, C-177 landed, and no historical line moved.
"""
import hashlib
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEDGER = r"D:\CIS\pipeline_reports\progress.md"
REPORT = r"D:\CIS\pipeline_reports\16_E5p_temporal_gnn.md"

raw = io.open(LEDGER, "rb").read()
print("=== LEDGER ===")
print("bytes %d  sha16 %s" % (len(raw), hashlib.sha256(raw).hexdigest()[:16]))
crlf = raw.count(b"\r\n")
lf_only = raw.count(b"\n") - crlf
cr_only = raw.count(b"\r") - crlf
print("CRLF %d   bare-LF %d   bare-CR %d" % (crlf, lf_only, cr_only))
print("=> line endings: %s"
      % ("ALL CRLF -- TEXT-MODE REWRITE WOULD HAVE DESTROYED THEM" if lf_only == 0 and crlf
         else "ALL LF (clean)" if crlf == 0 and cr_only == 0
         else "MIXED -- investigate"))

text = io.open(LEDGER, encoding="utf-8").read()
lines = text.split("\n")
print("lines %d" % (len(lines) - 1 if text.endswith("\n") else len(lines)))

print()
print("--- marker present? ---")
mk = "**[C-177"
print("marker occurrences: %d" % text.count(mk))
for i, ln in enumerate(lines, 1):
    if mk in ln:
        print("  :%d %s" % (i, ln[:150]))

print()
print("--- C-177 entry ---")
print("'## C-177' occurrences: %d" % text.count("## C-177"))
for i, ln in enumerate(lines, 1):
    if ln.startswith("## C-177"):
        print("  :%d %s" % (i, ln))

print()
print("--- historical anchors still at their line numbers? ---")
# The C-176 pass established these. If any moved, the marker insertion shifted
# the file and every citation into it is now off.
anchors = {6054: "C-172", 6055: "C-172", 6056: "C-172", 6168: "C-172", 6173: "C-172",
           6696: "C-177", 6705: ""}
for n, tag in sorted(anchors.items()):
    ln = lines[n - 1] if n - 1 < len(lines) else "<EOF>"
    print("  :%d %s" % (n, ln[:120]))

print()
print("=== REPORT ===")
rr = io.open(REPORT, "rb").read()
rt = io.open(REPORT, encoding="utf-8").read()
print("bytes %d  sha16 %s" % (len(rr), hashlib.sha256(rr).hexdigest()[:16]))
print("CRLF %d  bare-LF %d" % (rr.count(b"\r\n"), rr.count(b"\n") - rr.count(b"\r\n")))
print("header relabelled:    %s" % ("over the searched grid" in rt))
print("amendment inserted:   %s" % ("AMENDMENT (C-177" in rt))
print("old header still present anywhere: %s"
      % ("| max pooled at within-AUC \u2261 0.5 |" in rt))
rl = rt.split("\n")
for i, ln in enumerate(rl, 1):
    if "max pooled at within-AUC" in ln:
        print("  :%d %s" % (i, ln[:170]))
    if ln.startswith("**\u2605AMENDMENT (C-177"):
        print("  :%d %s" % (i, ln[:170]))
