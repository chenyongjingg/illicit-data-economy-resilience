# -*- coding: utf-8 -*-
"""C-177: every number in the refutation table is a LOWER BOUND, not a maximum.

THE ERROR IS IN A LABEL, WHICH IS WHY IT SURVIVED TWO REVIEWS.
Row (3,1,1,3) says "未超" -- a negative existential over a searched grid -- and the
peer correctly flagged that as "not found at this resolution", not "cannot". The
same defect sits on the headline row and on the table HEADER: "max pooled at
within-AUC = 0.5" asserts a maximum, and what was computed is the maximum over a
4-level scoring set. Measured gap for (2,2,2,2):

    L=3  0.562500    L=4  0.625000    L=5  0.656250    L=6  0.687500

Still rising at L=6, so the supremum is unknown and 0.625 is a WITNESSED LOWER
BOUND. The identity bounds it: for equal-rate bins pooled = (1+P12+P21)/4 <= 0.75.

The refutation is untouched -- one witness suffices, and 0.5625 at L=3 already
exceeds the 0.500 ceiling for equal-rate bins -- but the label over-claims, and a
label is what a reader who does not re-run the search will carry away.

THE PEER'S IDENTITY, VERIFIED BEYOND THE CASE IT TESTED. It proposed
    pooled = [0.5(q1^2 + q2^2) + q1*q2*(P12+P21)] / (q1+q2)^2     when p_i = lam*q_i
At lam = 1 this held to 0.0e+00 over 5 configs / 24,176 witnesses. But lam = 1
FORCES p = q, so that only ever exercised the equal-size family; the claim is
general in lam. Testing lam != 1 -- (2,4,1,2), (4,2,2,1), (1,2,2,4), (3,6,2,4),
(2,1,4,2), (1,3,2,6) -- it holds to 0.0e+00 over 6 more configs / 131,622
witnesses. It also explains the (1,1,3,3) plateau quantitatively: there it is
[5 + 3(P12+P21)]/16, and the observed 0.5625 pins the achievable P12+P21 at 4/3
against a theoretical 2 -- so the grid limits THAT configuration, which is a
reason, not just an absence.

This script edits the report's table header and inserts the correction at the
claim, then marks the ledger's C-172 table header and appends C-177.
"""
import hashlib
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPORT = r"D:\CIS\pipeline_reports\16_E5p_temporal_gnn.md"
LEDGER = r"D:\CIS\pipeline_reports\progress.md"

# ---------------- report: fix the header cell, add the correction in place ----
r = io.open(REPORT, encoding="utf-8").read()
OLD_HDR = "| bins (p1,q1,p2,q2) | rates | ceiling | max pooled at within-AUC \u2261 0.5 |"
NEW_HDR = ("| bins (p1,q1,p2,q2) | rates | ceiling | max pooled at within-AUC \u2261 0.5 "
           "**over the searched grid** (L=4; a LOWER bound \u2014 see below) |")
assert r.count(OLD_HDR) == 1, "report header not unique: %d" % r.count(OLD_HDR)
r = r.replace(OLD_HDR, NEW_HDR)

ANCHOR = ("within-bin AUC exactly 0.5 in both bins reaches pooled **0.625**.")
assert r.count(ANCHOR) == 1, "anchor not unique"
ADD = ANCHOR + """

**★AMENDMENT (C-177, same day): "max" above means max OVER THE SEARCHED GRID, and
the sup is not reached.** For (2,2,2,2) the value is 0.5625 / 0.625 / 0.65625 /
**0.6875** at L = 3 / 4 / 5 / 6 — still rising, so **0.625 is a witnessed lower
bound, not a maximum**, and the same caveat the (3,1,1,3) row earned ("not found
at this resolution") applies to every row including that one. The refutation is
unaffected — **one witness suffices, and 0.5625 at L=3 already exceeds the 0.500
ceiling** — but the label over-claimed, and a label is what a reader who does not
re-run the search carries away. The identity bounds it: for equal-rate bins
`pooled = (1 + P12 + P21)/4 <= 0.75`. **The peer's general form,
`pooled = [0.5(q1^2+q2^2) + q1*q2*(P12+P21)]/(q1+q2)^2` for `p_i = lam*q_i`, is
verified to 0.0e+00 over 6 configs / 131,622 witnesses at `lam != 1`** — at lam=1
it forces p=q, so the equal-size family is all it could ever have exercised."""
r = r.replace(ANCHOR, ADD)
io.open(REPORT, "w", encoding="utf-8", newline="").write(r)

# ---------------- ledger: mark C-172's over-claiming header, append C-177 -----
raw = io.open(LEDGER, "rb").read()
led = io.open(LEDGER, encoding="utf-8").read()
LHDR = "| \u7bb1\u914d\u7f6e (p1,q1,p2,q2) | \u6bd4\u7387 | \u4e0a\u9650\uff08t0 \u5355\u53d8\u91cf\u6700\u5927\u503c\uff09 | **within \u6052 0.5 \u65f6 pooled \u6700\u5927** | \u5224\u5b9a |"
LMARK = ("**[C-177\uff1a\u6b64\u5904\u300cmax\u300d\u662f\u300c\u641c\u7d22\u7f51\u683c\u5185\u7684\u6700\u5927\u300d\uff0c"
         "\u4e0d\u662f\u4e0a\u786e\u754c\uff1b\u4e0b\u6587 0.625 \u4e3a**\u5df2\u89c1\u4e0b\u754c**]** ")
assert led.count(LHDR) == 1, "ledger header not unique: %d" % led.count(LHDR)
led = led.replace(LHDR, LMARK + LHDR)

ENTRY = """

---

## C-177 — 2026-09-24 — ★**证伪表里的每个数都是「已见下界」，不是「最大值」**：
## 表头的「最大」一词是错的；(2,2,2,2) 在 L=3/4/5/6 为 0.5625/0.625/0.65625/**0.6875**
## **仍在上升** ⇒ 无任何可负担的网格给出上确界；★同侪的广义恒等式我在 **λ≠1** 上独立验证通过

### ① 错在**标签**，所以它躲过了两轮复核

同侪指出我表中 `(3,1,1,3)` 行的「未超」是**在网格上的否存在命题**，不是「不可能」。
**对。但同一缺陷在表头与头号行上，我两轮都没看见**：
表头写「within 恒 0.5 时 pooled **最大**」——**它断言了一个最大值**，
而算出的是**4 值网格上的最大值**。实测差：

| L | 3 | 4 | 5 | 6 |
|---|---|---|---|---|
| (2,2,2,2) max pooled | 0.562500 | 0.625000 | 0.656250 | **0.687500** |

**L=6 仍在上升 ⇒ 上确界未知，`0.625` 是「已见下界」。**
恒等式给出界：等率两箱 `pooled = (1+P12+P21)/4 ≤ 0.75`。

**⇒ 结论不受影响**（**一个见证就够了**，而 **L=3 的 0.5625 已超过等率箱的 0.500 上限**），
但**标签过度声明**，而标签正是**不重跑搜索的读者会带走的东西**。

### ② ★同侪的广义恒等式：我在**它没测的那一半**上验证通过

它提出：`p_i = λq_i` 时
`pooled = [0.5(q1²+q2²) + q1q2(P12+P21)] / (q1+q2)²`。

- λ=1 时：5 个配置 / 24,176 见证，`|pooled − 恒等式| = 0.0e+00`。
- **但 λ=1 会强制 p=q** ⇒ 那一半**只跑到了等大小族**，而它的主张是**一般 λ 的**。
- **λ≠1 的 6 个配置**（(2,4,1,2)、(4,2,2,1)、(1,2,2,4)、(3,6,2,4)、(2,1,4,2)、(1,3,2,6)）：
  `|pooled − 恒等式| = 0.0e+00`，**131,622 个见证** ⇒ **一般形式成立，不只是特例**。

**★它同时把我 (1,1,3,3) 的「平台」解释成了量**：那里是 `[5 + 3(P12+P21)]/16`，
而实测 0.5625 ⇒ **可达的 `P12+P21` 恰为 4/3**（理论上限 2）
⇒ **是网格限制住了那一个配置——这是理由，不只是一个「没找到」。**
**⇒ 同侪的表述优于我的**（我的是「最大」，它的是「为何这个配置上不去」）。

### ③ 更正清单（**更正须到达它所更正的对象**）

| 对象 | 处置 |
|---|---|
| 报告 `16_` §9(e) 表头 | **已改**：加「over the searched grid (L=4; a LOWER bound)」 |
| 报告 `16_` §9(e) 表下 | **已就地补 AMENDMENT**（含 L 表＋同侪恒等式与我的验证范围） |
| 台账 C-172 表头（`:6696`） | **已加行内标记**（指向本节） |
| `_tools/_refute_ceiling.py` | **已改**：改为**扫 L=3/4/5 并逐列打印**，表头写「LOWER BOUND」 |
| `_tools/_mark_c172_ledger*.py` | 不动（是当日已完成工序的见证） |

### ④ ★我自己的量具在本次验证里也犯了一次同族错（登记）

同侪自陈其量具把 `/4.0` 硬编码后用 16 个配对数喂入，得出 **AUC = 2.75**——
**AUC 大于 1 是自明的错**，所以它当场被发现；它由此立了
「先断言值域再报数」。
**我在同一次验证里打印了一列标签为 `cover?<=0.75`、而谓词实为「恒等式误差 < 1e-12」的列。**
**标签与谓词不一致** ⇒ 若我照标签引用，就会得到一句**我并未测量过的**「覆盖 ≤ 0.75 成立」。
**⇒ 我未引用该列。**
**⇒ 与 §9(h) 同族：标签/注释声称的行为与代码实际做的不一致。**
**比 AUC>1 更危险的正是这种**——它**不是自明的**，只有重跑才知道标签是错的。
"""
assert "## C-177" not in led, "C-177 already present"
io.open(LEDGER, "w", encoding="utf-8", newline="").write(led + ENTRY)

after = io.open(LEDGER, "rb").read()
assert after.startswith(raw), "LEDGER PREFIX CHANGED"
print("report: header relabelled + amendment inserted")
print("ledger: C-172 header marked + C-177 appended")
print("  ledger %d -> %d B ; sha16 %s -> %s"
      % (len(raw), len(after), hashlib.sha256(raw).hexdigest()[:16],
         hashlib.sha256(after).hexdigest()[:16]))
print("  ledger prefix preserved: OK")
print("  report size %d B" % len(io.open(REPORT, "rb").read()))
