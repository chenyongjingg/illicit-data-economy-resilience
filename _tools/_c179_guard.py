# -*- coding: utf-8 -*-
"""C-179: the budget guard in my own refutation tool had its exponents SWAPPED,
so it failed OPEN. Found because the tool ran for minutes emitting nothing.

    guard:   n_total ** L          ->  10 ** 6 = 1,000,000   < BUDGET -> admitted
    actual:  levels ** n_total     ->  6 ** 10 = 60,466,176  = 60x the budget

`itertools.product(range(levels), repeat=len(items))` enumerates `levels` to the
power of the ITEM COUNT. The guard tested the item count to the power of the
levels. Both are "a power of two numbers from the same call", which is exactly
why it reads as correct: the expression `n_total ** L` names the cost the way I
was thinking about it, and the thinking was what was wrong.

The failure direction matters. A guard that fails CLOSED costs a skipped cell and
is visible in the output. This one failed OPEN: it admitted a 60M-iteration loop,
so the cost landed as wall-clock with no output, and the only signal was silence.
Silence is indistinguishable from "still computing" -- so this is the same family
as rc3's launcher comment and the mislabelled table header, one level out: the
guard said "this is within budget" and the budget was never what it named.

Fixed, and the tool now PRINTS the cells it did not search, with their cost, so
a `skip` can never be read as a negative result. That is C-177's discipline
("a search reports a maximum only over the grid searched") applied to the tool's
own output rather than to its conclusion.
"""
import hashlib
import io
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEDGER = r"D:\CIS\pipeline_reports\progress.md"
TOOL = r"D:\CIS\_tools\_refute_ceiling.py"

t = io.open(TOOL, encoding="utf-8").read()
assert "cost = L ** n_total" in t, "the fix is not present"
assert "n_total ** L > 4_000_000" not in t, "the broken guard is still present"

raw = io.open(LEDGER, "rb").read()
led = io.open(LEDGER, encoding="utf-8").read()
assert "## C-179" not in led
ENTRY = """

---

## C-179 — 2026-09-24 — ★我自己的量具：**预算守卫的指数写反了**，且**朝「放行」方向失效**
## （`n_total ** L` 应为 `L ** n_total`）；发现方式是**它跑了几分钟、什么都不输出**

### ① 算式

| | 表达式 | (2,3,1,4) 在 L=6 |
|---|---|---|
| **守卫写的** | `n_total ** L` | `10 ** 6` = **1,000,000** < 4e6 ⇒ **放行** |
| **实际代价** | `L ** n_total` | `6 ** 10` = **60,466,176** ⇒ **超 60 倍** |

`itertools.product(range(levels), repeat=len(items))` 枚举的是
**`levels` 的「元素个数」次方**。守卫测的是**元素个数的「层数」次方**。
**两者都是「同一个调用里两个数的幂」——这正是它读起来像对的原因**：
`n_total ** L` 这个写法**按我当时的想法命名了代价**，错的是那个想法。

### ② ★失效**方向**才是要点

- **守卫若朝「拦住」方向失效**：代价＝少算一格，**输出里看得见**（`skip`）。
- **本例朝「放行」方向失效**：代价＝**几分钟的墙钟、零输出**。
  **唯一的信号是沉默，而沉默与「还在算」不可区分。**

**⇒ 与本日 §9(h) 的启动器注释、§9(e) 的表头标签同族，只是又往外一层**：
**守卫说「这在预算之内」，而预算从来不是它命名的那个东西。**

### ③ 处置：修守卫，**并让它打印自己没搜的格子**

新输出（实测，秒级完成）：

```
bins(p,q,p,q)        ceiling       L=3       L=4       L=5       L=6   verdict
(2, 2, 1, 3)        0.633333   0.666667   0.700000   0.700000   0.700000   **EXCEEDS ceiling**
(2, 2, 2, 2)        0.500000   0.562500   0.625000   0.656250   0.687500   **EXCEEDS ceiling**
(3, 1, 1, 3)        0.750000   0.750000   0.750000   0.750000   0.750000   not found at this resolution
(2, 3, 1, 4)        0.619048   0.642857   0.666667       skip       skip   **EXCEEDS ceiling**
(1, 2, 1, 3)        0.550000   0.600000   0.650000   0.650000   0.650000   **EXCEEDS ceiling**

NOT SEARCHED (budget 3000000 tuples; a `skip` cell is a statement about this
program's budget, NOT a negative result about the mathematics):
   bins=(2, 3, 1, 4) L=5 costs 5**10 = 9765625 tuples
   bins=(2, 3, 1, 4) L=6 costs 6**10 = 60466176 tuples
```

**⇒ 让 `skip` 无法被读成否定结论，正是 C-177 的纪律（「搜索只报告它所搜网格上的最大值」）
施加到**工具自己的输出**上，而不只是它的结论上。**

### ④ 附：L=6 补齐后的读数（**低层网格的行不随 L 变，不意味着它也是低层网格的性质**）

- `(2,2,2,2)` **仍在升**（0.5625 → 0.6875），**L=6 时 `P12+P21` = 1.75 / 2**，仍未取到理论值。
- `(2,2,1,3)`、`(1,2,1,3)` 在 **L=5 与 L=6 持平**（0.700000 / 0.650000）。
- `(3,1,1,3)` 在**四个层集上恒为 0.750000**，**恰等于它自己的上限** ⇒ 四层全部「未找到」。
- **⇒ 与 §6 的 `(1,1,3,3)` 一起看：停住与不停住都有，且都发生在等率或非等率两侧。**
  **⇒ 「它在某个 L 停住了」本身不构成「它是结构性的」——只有跨多个 L 持平才是证据，
  而即便如此也只是**到那个 L 为止**。**
"""
io.open(LEDGER, "w", encoding="utf-8", newline="").write(led + ENTRY)
after = io.open(LEDGER, "rb").read()
assert after.startswith(raw), "ledger prefix changed"
print("ledger: C-179 appended (%d -> %d B, %d lines)"
      % (len(raw), len(after), after.count(b"\n")))
print("tool guards verified: fixed form present, broken form absent")
