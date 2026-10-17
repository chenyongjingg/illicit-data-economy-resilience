# -*- coding: utf-8 -*-
"""Mark the three refuted-claim lines in the LEDGER (C-172 residue).

WHY THIS IS A SEPARATE PASS. C-172 corrected `_ceiling_check.py` (docstring and
runtime print), the report `16_` (four inline tags + §9(e)), and the memory
files. It did NOT reach `pipeline_reports/progress.md`, which carries the claim
three more times -- including at :6549, the OPERATIVE LANDING-TIME
PRE-REGISTRATION. A landing-time reader greps the ledger: that is what a
pre-registration is for. So the one line most likely to be read is the one line
still asserting the withdrawn oracle. Found by the peer, verified here at source
before acting (:6055, :6168, :6549 all confirmed live).

INLINE, NOT REWRITTEN. The original text stays; a marker is prefixed. Two
reasons: the ledger is append-only (editing a historical line is exactly the
thing this project forbids), and other instruments cite these lines BY NUMBER --
so the line COUNT is asserted unchanged and each target is asserted to still be
at its number after the edit.
"""
import hashlib
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEDGER = r"D:\CIS\pipeline_reports\progress.md"
MARK = "**[作废 — 已被穷举证伪，见 C-172 §①；该判据已撤回]** "

# (line number, a substring that must appear in that line)
TARGETS = [
    (6055, "在同一次运行里算术上不可能"),
    (6168, "与 within-t0 = 0.5 **算术上不可能**"),
    (6549, "算术上不可能** ⇒ 若出现即**写入器缺陷不是结果**"),
]

raw = io.open(LEDGER, "rb").read()
before_sha = hashlib.sha256(raw).hexdigest()[:16]
lines = io.open(LEDGER, encoding="utf-8").read().split("\n")
n_before = len(lines)

for ln, must in TARGETS:
    cur = lines[ln - 1]
    assert must in cur, "line %d does not carry %r -- refusing" % (ln, must[:40])
    assert MARK not in cur, "line %d already marked" % ln
    lines[ln - 1] = MARK + cur
    print("marked :%d" % ln)
    print("   %s" % lines[ln - 1][:150])

text = "\n".join(lines)
assert text.count("\n") == n_before - 1, "line count moved"
io.open(LEDGER, "w", encoding="utf-8", newline="").write(text)

# Re-read and assert: same count, each marker at its own number, prefix intact.
after = io.open(LEDGER, encoding="utf-8").read()
alines = after.split("\n")
assert len(alines) == n_before, "count changed: %d -> %d" % (n_before, len(alines))
bad = 0
for ln, must in TARGETS:
    ok = alines[ln - 1].startswith(MARK) and must in alines[ln - 1]
    bad += 0 if ok else 1
    print("  verify :%d %s" % (ln, "OK" if ok else "*** NOT OK ***"))

# The tail must be untouched (append-only discipline: everything after the last
# marked line is preserved byte-for-byte; nothing was inserted or removed).
print("\n  lines %d -> %d (must be equal)" % (n_before, len(alines)))
print("  size  %d -> %d B" % (len(raw), len(after.encode("utf-8"))))
print("  sha16 %s -> %s" % (before_sha,
                            hashlib.sha256(after.encode("utf-8")).hexdigest()[:16]))
sys.exit(1 if bad else 0)
