# -*- coding: utf-8 -*-
"""C-180: the grid maxima ARE the suprema -- now proven, not assumed. Plus the
enumeration bug that had to be found first, which exposed itself by returning a
maximum BELOW a value already measured.

WHAT UPGRADES. The peer's covering argument, which I verified: `auc` is a
function of pairwise >/=/< alone, so replacing each value by its rank among the
distinct values present preserves every AUC and the within-AUC==0.5 constraint.
Any real assignment therefore collapses into the L=n grid. So
    max over the L=n grid  ==  sup over ALL real scores.
That converts C-177's "witnessed lower bound" into a proven supremum -- and for
all five computable configurations the exact sup EQUALS the grid maximum, so the
numbers I corrected in C-177 were right; what was missing was the right to call
them suprema, which is now established rather than assumed.

THE BUG THAT CAME FIRST, AND ITS SELF-REFUTING SIGNATURE. The first version of
_sup_weakorder.py enumerated set partitions by restricted growth, which pins item
0 into the lowest class -- so only orderings with item 0 minimal were reached. It
enumerated Fubini(n-1) patterns while printing Fubini(n) as the count. It
reported sup = 0.593750 for (2,2,2,2), where the grid already gave 0.687500: a
claimed over-set producing a SMALLER maximum. That is self-refuting, so the
number never had to be trusted -- the same way AUC > 1 exposed the peer's
hardcoded /4.0. The corrected tool now ASSERTS its leaf count against
sum_k k!*S(n,k) = Fubini(n) before reporting anything.
"""
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPORT = r"D:\CIS\pipeline_reports\16_E5p_temporal_gnn.md"
LEDGER = r"D:\CIS\pipeline_reports\progress.md"

SECT = """**★★SECOND AMENDMENT (C-180): 上表里的数不是「下界」，是**已证的上确界**。**

**覆盖论证（同侪提出，我独立实现并验证）**：`auc` 只看成对的 `>`/`==`/`<`。
把每个取值换成**它在现存不同值中的排名**，三个 AUC 全不变，
`within-AUC ≡ 0.5` 的约束也不变 ⇒ **任何实数赋值都可投影进 (L=n) 格点**，故

> **(L=n) 格点上的最大值 =（全实数评分上的）上确界。**

**实现为 `_tools/_sup_weakorder.py`**（枚举**弱序**＝有序集划分），
**并自证枚举量**：叶数必须**逐位等于** `Σ_k k!·S(n,k) = Fubini(n)`
（n=4/6/8 实测 75 / 4683 / 545835 全对）。

| bins (p,q,p,q) | n | Fubini(n) | t0 上限 | **精确上确界** | 判定 |
|---|---|---|---|---|---|
| (2,2,1,3) | 8 | 545,835 | 0.633333 | **0.700000** | **超** |
| **(2,2,2,2)** | 8 | 545,835 | 0.500000 | **0.687500 = 11/16** | **超** |
| (3,1,1,3) | 8 | 545,835 | 0.750000 | **0.750000** | **不超（＝上限）** |
| (2,3,1,4) | 10 | 102,247,563 | 0.619048 | 未计算 | 见下 |
| (1,2,1,3) | 7 | 47,293 | 0.550000 | **0.650000** | **超** |
| (1,1,3,3) | 8 | 545,835 | 0.500000 | **0.562500 = 9/16** | **超** |

**三个结论：**

1. **五个可算配置上，精确上确界逐位等于格点最大值**
   ⇒ **C-177 里我改对了数值，缺的只是「叫它上确界」的资格**，而那资格**是证出来的，不是假定的**。
2. **★下界上升为上确界后，我 C-177 §② 那句话彻底倒了**：`(1,1,3,3)` 在**穷举枚举下仍为 0.5625**
   ⇒ 平台**是结构性的**，不是网格限制。同侪对此给了**证明**（`P12+P21 ≤ 4/3`）。
3. **★`(3,1,1,3)` 的精确上确界 = 0.750000 = 它自己的上限**
   ⇒ **在那一个配置上，「池化 > 上限」仍然能定罪**（同侪 item 4）。
   **⇒ 正确的边界是「上确界 = f(观测到的 within-AUC)」一个函数，不是一个阈值。**

**(2,3,1,4) 的上确界未计算**（Fubini(10)=102,247,563，超预算）——**不声称**。
**而它不需要**：同侪的见证给出 池化 = 2/3 > 0.619048，**一个见证就足以证伪**。

**★此外，一条关于本报告表格的同侪指控，已回源核实为误**：同侪 item 3 称我表中
`(2,3,1,4)` 在 L=4 列下印的是 `0.642857`。**实测我的该行：L=3 = 0.642857、**
**L=4 = 0.666667**，且同侪自己的见证（`pos1=[2,2], neg1=[3,2,0], pos2=[1], neg2=[1,1,1,1]`）
**在我的 `auc` 下逐位重现 14/21 = 0.666667**。⇒ **两人的数字全同，错的是列的归属**。
**此事已记入台账，不作平滑处理。**
"""

ENTRY = """

---

## C-180 — 2026-09-24 — ★★**格点最大值就是上确界**（「覆盖论证」，已证）
## ⇒ C-177 的「已见下界」升为**已证上确界**；★★但先必须先踩一个我自己的核算错：
## **枚举不全**（把项 0 钉死为最小），而它**自曝**的方式是返回了一个
## **低于已测格点值的「上确界」**

### ① 升级依据：覆盖论证（同侪提出，我独立实现）

`auc` 只看成对的 `>`/`==`/`<` ⇒ 把每个取值换成**它在现存不同值中的排名**，
**三个 AUC 全不变**，`within-AUC ≡ 0.5` 的约束也不变 ⇒ 任何实数赋值可投影进 (L=n) 格点

> **(L=n) 格点最大值 = 全实数评分上的上确界。**

**实现**：`_tools/_sup_weakorder.py`，枚举**弱序**（先用 restricted growth 枚举集划分，
**再对每个划分试遍其 k 个块的全部 k! 种排序**），
叶数 = `Σ_k k!·S(n,k) = Fubini(n)`。**工具在报告任何数之前先断言叶数逐位相等**。

### ② ★★先踩的坑：**第一版枚举不全，而它自曝**

第一版用了 restricted growth（`a[0]=0`、`a[i] ≤ 1+max(a[..i-1])`）
⇒ **它枚举的是集划分（Bell(n)）而非有序集划分**，
**等价于把项 0 钉死在最低类** ⇒ 只走到「项 0 为最小」的那一半。
它**枚举 Fubini(n-1) 而打印 Fubini(n)**。

**自曝的方式不是重读，是数值不可能**：

| 配置 | 第一版报的「上确界」 | 已测格点值 |
|---|---|---|
| (2,2,2,2) | 0.593750 | **0.687500** |
| (1,1,3,3) | 0.531250 | **0.562500** |
| (1,2,1,3) | 0.500000 | **0.650000** |

**一个声称包含格点的枚举，不可能返回比格点更小的最大值**
⇒ **它自己把自己证伪了，那个数从未需要被信任**。
**与同侪 `AUC = 2.75`（硬编码 `/4.0`）同一格式：值域自明地错。**

### ③ 精确上确界（工具已自证枚举量 75/4683/545835 全对）

| bins | n | Fubini(n) | t0 上限 | 精确上确界 | 判定 |
|---|---|---|---|---|---|
| (2,2,1,3) | 8 | 545,835 | 0.633333 | **0.700000** | 超 |
| **(2,2,2,2)** | 8 | 545,835 | 0.500000 | **0.687500 = 11/16** | 超 |
| (3,1,1,3) | 8 | 545,835 | 0.750000 | **0.750000** | **不超（＝上限）** |
| (2,3,1,4) | 10 | 102,247,563 | 0.619048 | 未计算 | 见下 |
| (1,2,1,3) | 7 | 47,293 | 0.550000 | **0.650000** | 超 |
| (1,1,3,3) | 8 | 545,835 | 0.500000 | **0.562500 = 9/16** | 超 |

**★五个可算配置上，精确上确界逐位等于我 C-177 里修正后的格点最大值**
⇒ **数值从头就对，缺的是「叫它上确界」的资格；现在那个资格是证出来的。**

**★★并且 `(3,1,1,3)` 的上确界恰等于它自己的上限 0.750000**
⇒ **在那一配置上，「池化 > 上限」仍能定罪**；**正确的边界是一个函数
`sup(a)`（a = 观测到的 within-AUC），不是一个阈值。**

### ④ 同侪的一条指控已回源核实为误（不平滑处理）

同侪 item 3 称本报告表中 `(2,3,1,4)` 在 L=4 列下印 `0.642857`。**实测**：
我的 L=3 = 0.642857、**L=4 = 0.666667**；且同侪自己的见证
（`pos1=[2,2], neg1=[3,2,0], pos2=[1], neg2=[1,1,1,1]`）**在我的 `auc` 下逐位重现
within-AUC (0.5, 0.5)、pooled 14/21 = 0.666667**。
⇒ **两人的数字全同，错的是列的归属（把 L=3 列读成 L=4）**。
**同侪 items 1/2/4 则有价值，其中 item 1 已由本节的穷举枚举独立验证。**

### ⑤ 纪律追加

**「我的枚举是全的」与「我的判据是对的」一样，必须被断言，不能被声称。**
本次做法：**先断言叶数 = Fubini(n)**，不等就 `exit 3`。
**凡一个声称包含对象 X 的工具，必须能被另一个已知的 X 元素验证**；
**本次验证它的就是那个已测的格点值。**
"""

r = io.open(REPORT, encoding="utf-8").read()
ANCHOR = ("verified to 0.0e+00 over 6 configs / 131,622 witnesses at `lam != 1`** — at lam=1\n"
          "it forces p=q, so the equal-size family is all it could ever have exercised.")
assert r.count(ANCHOR) == 1, "report anchor not unique: %d" % r.count(ANCHOR)
r = r.replace(ANCHOR, ANCHOR + "\n\n" + SECT.rstrip("\n"))
io.open(REPORT, "w", encoding="utf-8", newline="").write(r)
print("report: section 9(e) second amendment appended")

raw = io.open(LEDGER, "rb").read()
led = io.open(LEDGER, encoding="utf-8").read()
assert "## C-180" not in led
io.open(LEDGER, "w", encoding="utf-8", newline="").write(led + ENTRY)
after = io.open(LEDGER, "rb").read()
assert after.startswith(raw), "ledger prefix changed"
print("ledger: C-180 appended (%d -> %d B, %d lines)"
      % (len(raw), len(after), after.count(b"\n")))
