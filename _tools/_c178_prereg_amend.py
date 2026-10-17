# -*- coding: utf-8 -*-
"""C-178: amend the E5p pre-registration BEFORE the reading exists.

Timestamped while rc4 is still training, because the whole value of a
pre-registration is that it is not adjustable once the number arrives. Reading
the CURRENT writer's source (not the artefact) falsified one of my four
predictions outright and showed a second is unreachable for a reason unrelated
to the fix.

P4's VALUE (294) WAS TRANSCRIBED FROM AN ORPHANED FIELD.
  _server/53_E5p_temporal_gnn.py:692-693  n_exact  <- np.allclose(stored, by_le[True])
  _server/53_E5p_temporal_gnn.py:704-705  n_leq_ne_gt <- np.array_equal(by_le[True], by_le[False])
Two separate comparisons over two separate operand sets, so "the counter is
wired to n_exact_match" is excluded by the SOURCE, not by the numbers. And
:699-703 has the writer saying the PREVIOUS revision returned the stored-vs-gt
count under this name -- i.e. the old field was a DIFFERENT quantity. The
record confirms it: the old artefact has NO `n_stored_equals_gt` key, and the
current writer emits one at :713. So the old 294 is that other quantity's
reading and carries no baseline force for the new field.

P1 (n_exact_match 294 -> 300) HAS AN UNSTATED DEPENDENCY.
  :675-676  `if len(r) == 0 and len(r_sl) == 0: continue`
  :708      `n = len(addrs)`  -- n is 300 REGARDLESS of the skip
  :710      `n_mismatch = n - n_exact`
So a sampled address with no edges in either frame is SKIPPED from n_exact but
still counted in n => it lands in n_mismatch as if it were a mismatch. If any
such row is sampled, n_exact_match CANNOT reach 300 however perfect the fix is.
Falsifiable discriminator recorded below.
"""
import hashlib
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPORT = r"D:\CIS\pipeline_reports\16_E5p_temporal_gnn.md"
LEDGER = r"D:\CIS\pipeline_reports\progress.md"
PREREG = r"D:\CIS\_tools\_r17_9f.txt"

SECT = """### \u2463 \u2605\u843d\u5730\u524d\u4fee\u6b63\uff08C-178\uff0c**\u5199\u4e8e rc4 \u4ecd\u5728\u8bad\u7ec3\u65f6**\uff09\uff1a
### **P4 \u7684\u6570\u503c\u662f\u6211\u4ece\u300c\u5b64\u513f\u5b57\u6bb5\u300d\u8f6c\u6284\u7684\uff0c\u4e0d\u662f\u57fa\u7ebf**\uff1b
### \u5e76\u4e14 **P1\uff08294\u2192300\uff09\u5e26\u4e00\u4e2a\u6211\u6ca1\u5199\u51fa\u6765\u7684\u524d\u63d0**

**\u8bfb\u7684\u662f\u5f53\u524d\u5199\u5165\u5668\u7684\u6e90\u7801**\uff08`_server/53_E5p_temporal_gnn.py:616-715`\uff09\uff0c**\u4e0d\u662f\u4ea7\u7269**\u3002

#### \u2460 P4 \u4f5c\u5e9f\u4e3a\u300c\u503c\u9884\u8a00\u300d\uff0c\u66ff\u6362\u4e3a\u4e24\u6761\u66f4\u786c\u7684

| # | \u4e8b\u5b9e |
|---|---|
| 1 | `:692-693` `n_exact` \u7531 **`np.allclose(stored[i], by_le[True])`** \u8ba1 |
| 2 | `:704-705` `n_leq_ne_gt` \u7531 **`np.array_equal(by_le[True], by_le[False])`** \u8ba1 |
| 3 | **\u4e24\u4e2a\u64cd\u4f5c\u6570\u96c6\u3001\u4e24\u4e2a\u6bd4\u8f83\uff0c\u4e92\u4e0d\u76f8\u540c** \u21d2 **\u300c\u8be5\u8ba1\u6570\u88ab\u63a5\u6210 `n_exact_match`\u300d\u7684\u63a5\u7ebf\u5047\u8bbe\uff0c\u7531\u6e90\u7801\u76f4\u63a5\u6392\u9664**\uff0c\u4e0d\u5fc5\u518d\u7531\u6570\u503c\u8bc1 |
| 4 | `:699-703` \u5199\u5165\u5668\u81ea\u9648\uff1a**\u4e0a\u4e00\u7248\u628a `stored` \u4e0e `gt` \u91cd\u7b97\u6bd4\u8f83\u7684\u7ed3\u679c\uff0c\u7528\u8fd9\u4e2a\u540d\u5b57\u8fd4\u56de** \u21d2 **\u65e7\u5b57\u6bb5\u662f\u53e6\u4e00\u4e2a\u91cf** |
| **5** | **\u56de\u6e90\u65e7\u4ea7\u7269\u672c\u8eab**\uff1a\u65e7\u4ea7\u7269**\u6ca1\u6709 `n_stored_equals_gt` \u8fd9\u4e2a\u952e**\uff0c\u800c\u5f53\u524d\u5199\u5165\u5668\u5728 `:713` **\u4f1a\u8f93\u51fa\u5b83** \u21d2 **\u65e7 294 \u5bf9\u65b0\u5b57\u6bb5\u7684\u503c\u6ca1\u6709\u57fa\u7ebf\u6548\u529b\u3002** |

**\u21d2 \u539f P4\uff08\u300c\u5fc5\u987b\u4ecd\u4e3a 294\u300d\uff09\u4f5c\u5e9f\uff0c\u6362\u4e3a\uff1a**

- **\u65b0 P4a\uff08\u7ed3\u6784\uff09**\uff1a\u65b0\u4ea7\u7269**\u5fc5\u987b\u542b `n_stored_equals_gt`**\uff08\u65e7\u4ea7\u7269\u65e0\u6b64\u952e\uff09\u3002
  **\u7f3a\u5931 \u21d2 \u8dd1\u7684\u4e0d\u662f\u6211\u6539\u8fc7\u7684\u90a3\u4e2a\u5199\u5165\u5668\u3002**
- **\u65b0 P4b\uff08\u65b9\u5411\uff09**\uff1a`n_stored_equals_gt` **\u5fc5\u987b\u5c0f**\u3002
  stored \u643a `<= t0` \u7a97 \u21d2 \u5b83**\u4e0d\u5e94**\u7b49\u4e8e `> t0` \u91cd\u7b97\u3002
  **\u82e5\u5b83\u63a5\u8fd1 300\uff0c\u90a3\u662f\u6cc4\u6f0f\u4fe1\u53f7\uff0c\u987b\u67e5\uff0c\u4e0d\u5f97\u8bfb\u6210\u901a\u8fc7\u3002**
- **\u539f P4 \u7684\u610f\u56fe**\uff08\u8ba1\u6570\u4e0d\u5f97\u4e0e `n_exact_match` \u540c\u6e90\uff09**\u7531\u7b2c 3 \u6761\u6e90\u7801\u4e8b\u5b9e\u627f\u62c5**\uff0c\u6bd4\u6570\u503c\u66f4\u786c\u3002

**\u2605\u8fd9\u6b63\u662f\u9884\u6ce8\u518c\u8be5\u6709\u7684\u7528\u6cd5**\uff1a\u8bfb\u6e90\u7801**\u5728\u8bfb\u6570\u4e4b\u524d**
\u63a8\u7ffb\u4e86\u6211\u81ea\u5df1\u7684\u4e00\u6761\u9884\u8a00\u3002**\u82e5\u7b49\u4ea7\u7269\u843d\u5730\u518d\u6539\uff0c\u90a3\u5c31\u6210\u4e86\u4e8b\u540e\u8c03\u53c2\u3002**

#### \u2461 P1\uff08294\u2192300\uff09\u7684\u672a\u58f0\u660e\u524d\u63d0\uff1a**\u88ab\u8df3\u8fc7\u7684\u884c\u4f1a\u8ba1\u8fdb `n_mismatch`**

```
:675-676   if len(r) == 0 and len(r_sl) == 0: continue     # \u8be5\u884c\u4e0d\u8ba1\u5165 n_exact
:708       n = len(addrs)                                  # \u4f46 n \u6052\u4e3a 300
:710       n_mismatch = n - n_exact                        # \u21d2 \u88ab\u8df3\u884c\u843d\u5728 mismatch \u91cc
```

\u21d2 **\u82e5\u62bd\u5230\u4efb\u4e00\u300c\u4e24\u5e27\u90fd\u65e0\u8fb9\u300d\u7684\u5730\u5740\uff0c`n_exact_match`
\u65e0\u8bba\u4fee\u5f97\u591a\u597d\u90fd\u5230\u4e0d\u4e86 300\u3002**

**\u53ef\u5224\u7684\u9274\u522b\u5668\uff08\u5148\u5199\u4e0b\uff09**\uff1a
\u82e5\u843d\u5730\u540e\u8bfb\u5230 **`n_exact_match == 299` \u4e14 `n_mismatch == 1`**\uff0c
**\u5219\u67e5 `first_mismatches` \u662f\u5426\u4e3a\u7a7a**\uff1a
- **\u7a7a \u21d2 \u90a3\u4e00\u6761\u662f\u88ab\u8df3\u8fc7\u7684\u884c\uff08\u4e0d\u662f\u7f3a\u9677\uff09**\uff0c\u4fee\u6cd5\u5b8c\u5168\u6210\u529f\uff1b
- **\u975e\u7a7a \u21d2 \u662f\u771f\u5931\u914d\uff0c\u4fee\u6cd5\u672a\u547d\u4e2d\u771f\u56e0\u3002**

**\u2605\u4e0d\u5f97\u628a 299 \u76f4\u63a5\u8bfb\u6210\u5931\u8d25**\uff0c\u4e5f**\u4e0d\u5f97\u628a 300 \u5f53\u6210\u552f\u4e00\u7684\u6210\u529f\u5f62\u5f0f**\u3002
"""

# ---- report: insert at the end of section 9(f), before its closing rule ----
r = io.open(REPORT, encoding="utf-8").read()
ANCHOR = ("- \u4e8c\u8005**\u53ef\u4ee5\u540c\u65f6\u6210\u7acb**\uff08GAP \u5168\u5173\u800c\u9a71\u52a8\u5668\u4ecd FAIL\uff09"
          "\u2014\u2014\u90a3\u662f**\u534f\u8c03\u7f3a\u9677**\uff0c\n"
          "  \u4e0d\u662f\u77db\u76fe\uff1a**\u5224\u636e\u4e0e\u5b83\u5224\u7684\u5bf9\u8c61\u4e0d\u540c\u6b65**\u3002"
          "**\u672c\u8f6e\u4e0d\u6539 `run_pipeline.py`**\uff08\u6539\u95e8\uff1d\u6539\u5224\u636e\uff09\u3002")
assert r.count(ANCHOR) == 1, "report anchor not unique: %d" % r.count(ANCHOR)
r = r.replace(ANCHOR, ANCHOR + "\n\n" + SECT.rstrip("\n"))
io.open(REPORT, "w", encoding="utf-8", newline="").write(r)
print("report: section 9(f) amended (4 sub-sections)")

# ---- pre-registration file: append the same ----
raw_pre = io.open(PREREG, "rb").read()
io.open(PREREG, "a", encoding="utf-8", newline="").write("\n\n---\n\n" + SECT)
after_pre = io.open(PREREG, "rb").read()
assert after_pre.startswith(raw_pre), "prereg prefix changed"
print("prereg: appended (%d -> %d B)" % (len(raw_pre), len(after_pre)))

# ---- ledger: append C-178 ----
raw = io.open(LEDGER, "rb").read()
led = io.open(LEDGER, encoding="utf-8").read()
assert "## C-178" not in led
ENTRY = """

---

## C-178 — 2026-09-24 — ★**落地前**修正我自己的预注册（写于 rc4 仍在训练时）：
## P4 的 294 是**从孤儿字段转抄的**，不是基线；P1 的 300 带一个未声明前提
## （被跳过的行会计进 `n_mismatch`）；★预注册的正确用法＝**读源码在读数之前推翻预言**

### ① 触发：我读了**当前写入器的源码**，而不是等产物

`_server/53_E5p_temporal_gnn.py:616-715`：

| 行 | 事实 |
|---|---|
| `:692-693` | `n_exact` ← `np.allclose(stored[i], by_le[True])` |
| `:704-705` | `n_leq_ne_gt` ← `np.array_equal(by_le[True], by_le[False])` |
| **`:` 结论** | **两个操作数集、两个比较** ⇒ C-173 §② 那个「该字段可能被接成 `n_exact_match`」的接线假设**由源码直接排除** |
| `:699-703` | 写入器自陈：**上一版把 stored-vs-gt 的结果用这个名字返回** |
| `:713` | 当前写入器**输出 `n_stored_equals_gt`** |

### ② ★判别证据在**旧产物本身**：旧产物**没有** `n_stored_equals_gt` 这个键

⇒ **旧字段是上一个量**，其 294 **对新字段的值没有基线效力**。
**⇒ 我的 P4（「必须仍为 294」）作废**——**我把一个新量的预言，写成了旧量的读数。**

**替换为**：**P4a** 新产物必须**含 `n_stored_equals_gt`**（缺则跑的不是我改的写入器）；
**P4b** 该值**必须小**（stored 携 `<= t0` 窗，不应等于 `> t0` 重算）；
**接近 300 ⇒ 泄漏信号，须查，不得读成通过。**

### ③ P1 的未声明前提：**被跳过的行会计进 `n_mismatch`**

`:675-676` 跳过「两帧都无边」的行 ⇒ 不入 `n_exact`；而 `:708` `n = len(addrs)` 恒为 300、
`:710` `n_mismatch = n - n_exact` ⇒ **该行落在 mismatch 里，虽然它从未被比较**。
**⇒ 抽到任何一行这样的地址，`n_exact_match` 就永远到不了 300，与修法好坏无关。**

**先写下鉴别器**：若读到 **299 / n_mismatch 1**，则**看 `first_mismatches` 是否为空**——
**空 ⇒ 是被跳过的行，修法完全成功；非空 ⇒ 真失配。**
**不得把 299 直接读成失败，也不得把 300 当成唯一成功形式。**

### ④ ★本轮方法上唯一值得推广的一条

**预注册的价值全在于它不能在读数之后调整。** 我这次是**读源码**（而非产物）
推翻了自己的一条预言，**时间戳在产物存在之前**。
**若等落地再改，同样的修改就成了事后调参。**
**⇒ 纪律：预注册写就之后到读数到手之前，是**唯一**可以合法修改它的窗口，
且每次修改必须带时刻与理由。**
"""
io.open(LEDGER, "w", encoding="utf-8", newline="").write(led + ENTRY)
after = io.open(LEDGER, "rb").read()
assert after.startswith(raw), "ledger prefix changed"
print("ledger: C-178 appended (%d -> %d B, %d lines)"
      % (len(raw), len(after), after.count(b"\n")))
