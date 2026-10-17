# -*- coding: utf-8 -*-
"""Second marker pass on the C-172 withdrawal: the STEP, and the scope of a header.

THREE MARKERS, THREE DIFFERENT PROBLEMS.

:6054  The invalid STEP itself. C-172 §② is precise that the ceiling is fine and
       the equivocation is the next sentence: "not constant within bins" =>
       "within-t0 AUC > 0.5" is the part that fails. The first pass marked the
       CONSEQUENCE at :6055 and left the inference that produces it unmarked --
       so a reader arriving at the reasoning meets it unflagged.

:6056  "这是重跑可以用的一致性判据，此前没有。" is now simply false: the
       criterion was withdrawn. Not a step, a claim about availability.

:6168  A SCOPE ERROR IN MY OWN MARKER. Pass 1 put a bare "该判据已撤回" on a
       BLOCK HEADER. The header sentence dies, but the two branch rules beneath
       it do not die together:
         bullet 1 -- "within-t0 >0.5 => `shuffled_control_at_chance` fails =>
                     feature/model channel" -- SURVIVES IN SUBSTANCE. Under the
                     fixed writer that flag IS computed from the within-t0 column
                     (:1401-1404), so it is the operative metric and a False there
                     is a real reading about the control.
         bullet 2 -- "(pooled ~0.84, within-t0 ~0.5) => writer defect" -- is the
                     withdrawn oracle and dies entirely.
       A bare 作废 over the header would tell a reader to discard a live rule.
       (Same defect C-166 names: a dismissal stated once, under a heading, reads
       as covering everything beneath it. Mine, this time.)

:6173 gets its own marker because bullet 2 is the one line that must never be
read as live -- it is the pre-registered oracle that would have turned "the fix
worked" into "the writer is broken".

THE PEER'S TWO EXTRA REFERENCES WERE OFF BY ONE; MINE ARE READ FROM THE FILE.
It cited :6053 and :6057, which are BLANK lines here. The step is :6054 and the
availability claim :6056. Line count is asserted unchanged so every existing
citation stays valid, and each target is asserted to sit at its own number.
"""
import hashlib
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEDGER = r"D:\CIS\pipeline_reports\progress.md"

STEP = "**[作废 — 第二步已被穷举证伪，见 C-172 §②]** "
AVAIL = "**[已失效 — C-172：该「一致性判据」已撤回]** "
ORACLE = ("**[整条作废 — 该「缺陷预言机」已撤回（C-172 §④）："
          "(池化≈0.84, within-t0≈0.5) 不是矛盾，而是修法奏效的特征]** ")

OLD_HDR = "**[作废 — 已被穷举证伪，见 C-172 §①；该判据已撤回]** "
NEW_HDR = ("**[前提已撤回（C-172 §①）—— 但下方分支不随之整条作废：第 1 条关于 "
           "`shuffled_control_at_chance` 的读法在修复版写入器下仍有效（该判据由 "
           "within-t0 列算出，:1401-1404）；第 2 条（写入器缺陷）整条作废]** ")

PREFIX = [(6054, STEP, "残差为正 ⇒ 对照的分数在箱内不恒定"),
          (6056, AVAIL, "这是重跑可以用的一致性判据"),
          (6173, ORACLE, "写入器缺陷，不是结果")]

raw = io.open(LEDGER, "rb").read()
sha_before = hashlib.sha256(raw).hexdigest()[:16]
lines = io.open(LEDGER, encoding="utf-8").read().split("\n")
n_before = len(lines)

for ln, mark, must in PREFIX:
    cur = lines[ln - 1]
    assert must in cur, "line %d lacks %r" % (ln, must[:30])
    assert not cur.startswith("**[作废") and not cur.startswith("**[已失效"), \
        "line %d already marked" % ln
    lines[ln - 1] = mark + cur
    print("prefixed :%d" % ln)

# refine my own over-broad marker at :6168 (my annotation, not history)
assert lines[6167].startswith(OLD_HDR), "unexpected :6168 prefix"
lines[6167] = NEW_HDR + lines[6167][len(OLD_HDR):]
print("refined  :6168")

text = "\n".join(lines)
io.open(LEDGER, "w", encoding="utf-8", newline="").write(text)

after = io.open(LEDGER, encoding="utf-8").read().split("\n")
assert len(after) == n_before, "line count moved %d -> %d" % (n_before, len(after))
bad = 0
for ln, mark, must in PREFIX:
    ok = after[ln - 1].startswith(mark) and must in after[ln - 1]
    bad += 0 if ok else 1
    print("  verify :%d %s" % (ln, "OK" if ok else "*** NOT OK ***"))
ok = after[6167].startswith(NEW_HDR) and "第 2 条（写入器缺陷）整条作废" in after[6167]
bad += 0 if ok else 1
print("  verify :6168 %s" % ("OK" if ok else "*** NOT OK ***"))
print("\nlines %d -> %d ; sha16 %s -> %s"
      % (n_before, len(after), sha_before,
         hashlib.sha256(io.open(LEDGER, "rb").read()).hexdigest()[:16]))
sys.exit(1 if bad else 0)
