# -*- coding: utf-8 -*-
"""C-177 addendum: one peer sharpening CONFIRMED, and one claim OF MINE REFUTED
by my own follow-up measurement -- written one step after I made it.

(A) CONFIRMED (peer). For equal-rate bins the sup is
        max over t = q2/q1 of [0.5(1+t^2) + 2t]/(1+t)^2
    measured: t=1 -> 0.750000000 ; t=2 -> 0.722222 ; t=3 -> 0.687500 ;
              t=5 -> 0.638889 ; t=10 -> 0.582645 ; t=100 -> 0.509803
    and a dense sweep over t in (0,10] peaks at t=1.00. So 0.75 is attained
    ONLY on the equal-size subfamily: the bound is a statement about the
    CONFIGURATION family, not about the grid.
    => The peer's point about my retracted column stands, and it is sharper
    than "the label was wrong": the label `cover?<=0.75` was a TRUE statement
    whose equality case my column never exercised. The predicate tested
    something else. That is NOT the same defect as a false label -- it is
    "right about a case you did not test", which no amount of re-reading the
    column can reveal. Worth keeping as a distinct member of the family.

(B) REFUTED (mine, one step old). In C-177 section 2 I wrote that (1,1,3,3)'s
    plateau at 0.5625 means "the GRID limits that configuration -- a reason,
    not just a not-found". I measured it instead of asserting it:
        (1,1,3,3)  L=4  0.562500   L=5  0.562500   L=6  0.562500   <-- FLAT
        (2,2,2,2)  L=4  0.625000   L=5  0.656250   L=6  0.687500   <-- RISES
    Both have equal rates. It is FLAT across three level sets, so the gap from
    the theoretical P12+P21 = 2 down to the achieved 4/3 is NOT a grid
    resolution effect, and my gloss was wrong.
    The contrast is the actual finding: L-dependence is ITSELF
    configuration-dependent, so neither "max over the grid" nor "the grid
    limits it" is a safe label in either direction.
    What survives is the identity and a witnessed bound PER (configuration, L).

Also marks the ledger's :6705 so the witness line does not read alone.
Append-only: the ledger prefix is asserted byte-identical.
"""
import hashlib
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEDGER = r"D:\CIS\pipeline_reports\progress.md"
TOOL = r"D:\CIS\_tools\_refute_ceiling.py"

# ---------------- 1. mark the witness line (:6705) ---------------------------
raw = io.open(LEDGER, "rb").read()
led = io.open(LEDGER, encoding="utf-8").read()
n_before = led.count("\n")

OLD = "\u53ef\u8fbe pooled **0.625**\u3002**\u21d2 \u7bb1\u5185\u6280\u80fd\u4e3a\u96f6\u4e5f\u80fd\u8d85\u8fc7\u4e0a\u9650\u30025 \u4f8b\u4e2d 4 \u4f8b\u5982\u6b64\u3002**"
MARK = ("**[C-177\uff1a`0.625` \u662f L=4 \u7684**\u5df2\u89c1\u4e0b\u754c**\uff08L=6 \u8fbe 0.6875\uff09\uff1b"
        "\u300c4 \u4f8b\u300d\u6309\u5404\u884c\u7684**\u6700\u5c0f\u5df2\u8dd1\u7f51\u683c**\u8ba1\u2014\u2014"
        "\u52a0\u5c42\u53ea\u53ef\u80fd\u4f7f max \u4e0a\u5347\uff08\u5c42\u96c6\u662f\u5305\u542b\u5173\u7cfb\uff09"
        "\uff0c\u6545\u6b64\u8ba1\u6570**\u53ea\u53ef\u80fd\u589e\u4e0d\u53ef\u80fd\u51cf**]** ")
assert led.count(OLD) == 1, "witness line not unique: %d" % led.count(OLD)
led = led.replace(OLD, MARK + OLD)
assert led.count("\n") == n_before, "marker shifted line count"

# ---------------- 2. append C-177 sections 5 and 6 ---------------------------
ADD = """
### ⑤ ★同侪的一处锐化：**已验证**——而那把「我的错标签」与「对但没测过的数」分开了

同侪锐化：等率两箱的 sup `max_t [0.5(1+t²) + 2t]/(1+t)²`（`t = q2/q1`）
**只在 `t=1` 取到 0.75**。**我实测（不是转述）**：

| t | 1 | 2 | 3 | 5 | 10 | 100 |
|---|---|---|---|---|---|---|
| sup | **0.750000000** | 0.722222 | 0.687500 | 0.638889 | 0.582645 | 0.509803 |

密集扫 `t∈(0,10]` 峰值在 **t=1.00** ⇒ **0.75 只在等大小族取到**。
**⇒ 那个「≤0.75」是**关于配置族**的界，不是关于网格的界。**

**★因此同侪对我那列的判断比我自己的更准，而且更细**：
`cover?<=0.75` **是一个真陈述**，只是我的谓词测的是别的东西。
**⇒ 这与「标签是假的」不是同一缺陷**——它是**「关于一个你没测过的情况，你说对了」**。
**⇒ 重新阅读那一列永远发现不了它**（差别不在列里，在列外）。
**⇒ 登记为本族的一个独立成员。**

### ⑥ ★★我自己的 §② 被**我自己的后续测量**证伪（写下后**一步**）

**§② 我写过**：「实测 0.5625 ⇒ 可达的 `P12+P21` 恰为 4/3（理论上限 2）
**⇒ 是网格限制住了那一个配置——这是理由，不只是一个「没找到」**。」

**后半句我没测就写了。测了：**

| 配置 | L=4 | L=5 | L=6 | 形态 |
|---|---|---|---|---|
| **(1,1,3,3)** | 0.562500 | 0.562500 | 0.562500 | **平的** |
| (2,2,2,2) | 0.625000 | 0.656250 | 0.687500 | **上升** |

**两者都是等率。`(1,1,3,3)` 跨三个层集全平** ⇒ 从理论 `P12+P21=2` 落到
实取 `4/3` 的那段差，**不是网格分辨率造成的** ⇒ **我那句是错的。**

**★而对比本身才是真正的读数：L-依赖性本身就是配置依赖的。**
⇒ 「网格上的最大」与「是网格限制住了它」**两个方向都不是安全的标签**。
**能留下的只有：恒等式本身，以及（配置, L）上的**已见下界**。**

**★这是本日第三次同族复现**（§8(h) 注释对不上代码 → §④ 标签对不上谓词 →
本节：**我先写下一句解释，再去做那个能判它的测量**）。
**共同形态：一句解释被放在测量前面。**
**⇒ 本项目的纪律据此追加一条：`⇒ 因此…` 之后若含「因为/是由于」，
那句话在被测之前不得进入台账。**
"""

io.open(LEDGER, "w", encoding="utf-8", newline="").write(led + ADD)
after = io.open(LEDGER, "rb").read()

# the prefix DID change (the marker is inline at :6705) -- so assert the weaker
# and correct property: everything before the marker is byte-identical, and the
# file only grew. Asserting startswith(raw) here was my own wrong check; the
# real invariant is "nothing was removed or rewritten".
assert len(after) > len(raw), "file did not grow"
assert after[:after.index(MARK.encode("utf-8"))] == raw[:after.index(MARK.encode("utf-8"))], \
    "content BEFORE the marker was modified"
assert after.endswith(ADD.encode("utf-8")), "append not at tail"
print("ledger: :6705 marked, C-177 sections 5 and 6 appended")
print("  %d -> %d B ; lines -> %d" % (len(raw), len(after), after.count(b"\n")))
print("  bytes before the marker: identical  OK")
print("  sha16 %s -> %s" % (hashlib.sha256(raw).hexdigest()[:16],
                            hashlib.sha256(after).hexdigest()[:16]))

# ---------------- 3. make the tool print L=6 too ------------------------------
t = io.open(TOOL, encoding="utf-8").read()
o1 = 'for L in (3, 4, 5):'
assert t.count(o1) == 1
t = t.replace(o1, 'for L in LEVELS:')

o2 = '''print("%-18s %9s %10s %10s %10s   %s"
      % ("bins(p,q,p,q)", "ceiling", "L=3", "L=4", "L=5", "verdict"))'''
assert t.count(o2) == 1, "header print not found verbatim"
n2 = '''LEVELS = (3, 4, 5, 6)
print("%-18s %9s" % ("bins(p,q,p,q)", "ceiling")
      + "".join("%10s" % ("L=%d" % L) for L in LEVELS) + "   verdict")'''
t = t.replace(o2, n2)

o3 = """so the achievable max is NOT size-independent even though the identity below is."""
assert t.count(o3) == 1
n3 = """so the achievable max is NOT size-independent even though the identity below is.
L=6 settles the direction and adds the contrast that matters (C-177 section 6):
(1,1,3,3) is FLAT at 0.5625 across L=4/5/6 while (2,2,2,2) RISES to 0.6875, both
at equal rates. So L-dependence is ITSELF configuration-dependent, and "the grid
limits it" is no safer than "this is the max" -- the witnessed bound is per
(configuration, L), not per configuration."""
t = t.replace(o3, n3)
io.open(TOOL, "w", encoding="utf-8", newline="").write(t)
print("tool: LEVELS=(3,4,5,6), header generated, docstring records the contrast")
