# -*- coding: utf-8 -*-
"""Repair the backtick-eating damage from a bash `-c` patch (G-67).

WHY A FILE. The previous patch was issued as `python -u -c "..."` inside double
quotes, so every backticked span in the REPLACEMENT text was command-substituted
by bash before python ever saw it. The `old` strings matched (count==1 asserts
passed) and the write succeeded -- so the tool reported success while writing a
sentence with `weighted`, `:471` and `npi*pair` silently deleted. That is the
same class as G-67: the shell ate a layer.

So: repair, then ASSERT on the bytes, and print a sha of the file so the fix is
witnessed rather than described.

The deliverable is the corrected line, not the story about how it broke.
"""
import hashlib
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOPIC = "cis-blackmarket-resilience-sprint.md"
MEM = "MEMORY.md"

BROKEN = ("  **★字段  加权的是箱大小**（）"
          "**，不是能闭合分解的配对数 **（该均值未报）")
FIXED = ("  **★字段 `weighted` 加权的是箱大小**（`:471`）"
         "**，不是能闭合分解的配对数 `npi·nni`**"
         "（该均值未报）")

t = io.open(TOPIC, encoding="utf-8").read()
n = t.count(BROKEN)
assert n == 1, "broken span not unique/found: %d" % n
t = t.replace(BROKEN, FIXED)
io.open(TOPIC, "w", encoding="utf-8", newline="").write(t)

# Now assert every correction is actually present, byte-exactly.
t = io.open(TOPIC, encoding="utf-8").read()
checks = [
    ("pull-withdrawn line", "★★已撤回（C-172）"),
    ("variation not sufficiency", "箱内变异是箱内判别的必要非充条件"),
    ("4-of-5 enumeration", "穷举 5 例中 4 例超上限"),
    ("not-a-contradiction", "**(pooled ≈0.84, within-t0 ≈0.5) 不是矛盾"),
    ("weighted is bin size", "字段 `weighted` 加权的是箱大小"),
    ("pair count named", "`npi·nni`"),
    ("repair: no empty parens left", "小**（）"),
]
bad = 0
for label, s in checks:
    hit = s in t
    if label.startswith("repair"):
        hit = not hit
    if not hit:
        bad += 1
    print("  %-28s %s" % (label, "OK" if hit else "*** NOT OK ***"))

m = io.open(MEM, encoding="utf-8").read()
mchecks = [
    ("M: withdrawal note", "C-172 穷举"),
    ("M: no defect oracle", "不得再当作「写入器缺陷」的预言机"),
    ("M: variation necessary-not-sufficient",
     "变异是必要非充分"),
    ("M: no longer claims >0.5", "其 within-t0 必然 >0.5"),
]
for label, s in mchecks:
    hit = s in m
    want = not label.endswith(">0.5")
    if hit != want:
        bad += 1
    print("  %-28s %s" % (label, "OK" if hit == want else "*** NOT OK ***"))

for p in (TOPIC, MEM):
    b = io.open(p, "rb").read()
    print("\n%-38s %d B  sha256=%s" % (p, len(b), hashlib.sha256(b).hexdigest()[:16]))
print("\n%d problem(s)" % bad)
sys.exit(1 if bad else 0)
