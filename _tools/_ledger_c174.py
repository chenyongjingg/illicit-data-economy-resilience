# -*- coding: utf-8 -*-
"""Append C-174 (the rc2 crash), C-175 (the launcher defect), C-176 (carriers).

Append-only: the existing prefix is asserted unchanged by sha before and after.
The standing rule is that a FAILED job gets a dated correction entry written
AFTER reading its log -- the log was read (pod traceback, frame by frame), not
transcribed from a summary of it.
"""
import hashlib
import io
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEDGER = r"D:\CIS\pipeline_reports\progress.md"
ENTRY = """

---

## C-174 — 2026-09-24 — ★★E5p 重跑（rc2）**崩溃、无产物**：`ValueError: multi_class
## must be in ('ovo', 'ovr')`；**根因是我自己的修复引入的缺陷**（`wtauc` 未切列）；
## ★教训：fixture 纪律只施于落地工具，未施于写入器改动——崩的分支就是没被控制的分支

### ① 事实（回源：pod 日志逐帧，非转述）

- 重跑 rc2 崩于 **2636.5s**（`lstart` 03:34:54Z），**`/root/cis/results/53_E5p_result.json`
  不存在** ⇒ **无任何产物可落地**。崩溃日志已保存为
  `logs/53_full_rc2_wtauc_crash_20260924.log`（sha256 `502cb3be…`，89 行，4974 B）。
- **对象同一性已核**：本地 `_server/53_E5p_temporal_gnn.py`
  sha256 = `1ebf15e85fe73026…`（79,168 B，1593 行）＝ pod `/root/cis/scripts/` 同一文件
  ⇒ **本地副本就是跑的那个对象**，不存在同名不同物。

### ② 逐帧 traceback（写入器自身的行号）

```
:1593  sys.exit(main())
:1345  test_within_t0_auc_by_delta={str(D): wtauc(te_m, k, lk["scores"]) ...
:1321  return within_t0_auc(t0v[m], Y[m, k], scores[m])
 :467  a = auc(y[m], s[m])
 :426  return float(roc_auc_score(y, s))
ValueError: multi_class must be in ('ovo', 'ovr')
```

### ③ 根因：**我加的那一行没切列**

`wtauc` 拿到的是**整块二维分数矩阵** `(n, n_deltas)`。`within_t0_auc` 用**箱掩码**
索引它所收到的任何东西 ⇒ `s[m]` 形状 `(n_in_bin, 3)`。≤2 列时 sklearn 无异议，
但 **>2 列**时 `roc_auc_score` 走 **multiclass 分支**，而 `multi_class` 默认 `"raise"`
⇒ 抛该错。报错信息**既没点名那一行，也没给出形状**，所以它花了 44 分钟才被找到，
而它**在第 0 秒就可判**。

**紧邻的下一行作了正确示范**：`:1342` 的 `test_auc_by_delta` 写了
`lk["scores"][te_m & OK[:, k], k]`——**同一字典、同一 k、带了列索引**。新加的那行没有。

### ④ 为什么三个臂没崩（**不得读成「旧写入器也有此问题」**）

臂走 `eval_block`（`:504`），传的是**一维**分数 ⇒ 该路径在旧写入器里**从未被走到**：
旧写入器**从不对任何 control 调 `wtauc`**（那正是本次修复的内容）。
⇒ **崩溃只存在于修复引入的代码路径内**，它**不是**关于旧写入器的证据。

### ⑤ 代价与账

- 2636.5s ≈ 44 分钟训练全部作废（进程亡、无中间产物、无断点续跑）。
- **★六个 GAP 的预言仍未被检验。** 运行死于写盘之前 ⇒ **对它们不得作任何陈述**，
  无论正反。「预期 0 条 GAP」仍然是**预言**，不是读数。

### ⑥ ★教训（本轮最值得留的一条）

**我把 fixture 纪律施加到了落地工具上，没有施加到写入器改动上。**
`80_e5p_landing.py` 的 `archive_once` / `place_canonical` / `bind_text_report`
各有成套 fixture（三分支 / 三分支 / 六例，含阳性对照）；`81_` 的驳回域也有 fixture。
**而这次改写入器，一套 fixture 都没有**——于是崩掉的分支，恰好就是没被控制的那一支。
**⇒ 规则：凡改写入器，先让**新路径**在本地以最小输入跑通（形状级 fixture 即可），
再上 pod；「只改了 compat/形状」不是免测理由，形状错误正是它引来的。**

### ⑦ 修复（两处，不是一处）

| 位置 | 改动 |
|---|---|
| 调用方 `wtauc` end | `scores[m]` → **`scores[m, k]`** |
| 被调方 `within_t0_auc` 入口 | 新增**一维守卫**：非一维即抛带形状与成因的错误 |

第二处是**把 44 分钟后的隐晦报错前移到入口**。**并把 44 分钟后的那一行留在消息里**，
使下一个人不必再跑一次才知道。

**验证对象 = 两个真实文件**（不是复述）：pre-fix = `_revisions/…1ebf15e8.py`，
post-fix = `_server/…py`（sha **`077cb37906477179`**），各自独立解析。
五例控制表：

| 例 | 对象/输入 | 结果 | 判定 |
|---|---|---|---|
| A | **pre-fix** ＋ 二维 | `ValueError: multi_class must be in ('ovo','ovr')` | **复现崩溃** |
| B | post-fix ＋ 二维 | `within_t0_auc takes 1-D labels and scores; got y.shape=(300,) s.shape=(300, 3)` | 守卫有驳回分支 |
| C | post-fix ＋ 单列 | `weighted=0.51554` | 修好 |
| D | post-fix ＋ 一维（臂） | `weighted=0.51554` | 臂不受影响 |
| E | **pre-fix** ＋ 单列 | `weighted=0.51554` | **A 是形状问题，不是修复问题** |

**C = D = E 三值逐位相同** ⇒ 修复在旧代码本来能工作的地方**行为不变**，
它唯一改变的是**对坏输入的拒绝**。**B 证明守卫不是字面量：它被走到并抛了。**

**★顺带证伪一个我自己的 fixture 写法**：第一版 fixture 让 pre/post 共用**同一棵
parse tree** 与同一个 `text` 变量，而 `ast.get_source_segment(text, node)` 是按
`node` 的偏移去**当时**的 `text` 里取片段的 ⇒ 改动点**之后**的函数**被静默截断**
（丢了全部 `return`，返回 None）。**量具随被测物漂移的 fixture，对两者都不作数。**

### ⑧ 处置时间线

| 时刻（UTC） | 事件 |
|---|---|
| 03:34:54 | rc2 起 |
| 04:18:58 | rc2 崩（2636.5s） |
| 04:19–04:22 | 定位、修复、五例控制、存 `_revisions/077cb379…`、推 pod 并核 sha |
| 04:22:23 | rc3 起（**1 分钟后因启动器缺陷中止**，见 C-175） |
| 04:23:37 | **rc4 起**（正确截断日志，pid 40251） |

---

## C-175 — 2026-09-24 — ★启动器缺陷：**注释声称截断了日志，代码里没有那条语句**；
## ⇒ 上一轮崩溃日志残留在活日志中，且**它自带 `RSC_EXIT=1`** ⇒ 任何数该标记的守卫
## 会在第一拍就读到「已结束」——**且指向错误的那个运行**

### ① 现象与算术

rc3 起于 04:22:23，1 分钟后查活日志：**98 行**。
**89（rc2 残留，含其自身的 `RSC_EXIT=1`）＋ 4（rc3 头）＋ 5（rc3 已产出）＝ 98**，
**逐项吻合** ⇒ 该文件**没有被截断**，rc3 是**追加**上去的。

### ② 根因：**注释描述了一个代码没有实现的动作**

rc3 启动器（`_run_53_full_rc3.sh`）正确地**保存**了 rc2 崩溃日志，其注释写着
「refusing to truncate the live log」——**但 `: > "$LOG"` 这条语句根本没被写出来**。
**一个声称了行为、而代码并不实现的注释**，与本项目已登记的「字面量无法追踪行为」
（写入器里写死的 `selection_was_blinded_to_true_labels=True`）**同族**：
两者都会让**读注释的人**相信一个**未被执行的**保证。

### ③ 后果（不只是不整洁）

`_wait_e5p.py` 的终局判定是 `grep -c "RSC_EXIT="`。
rc2 残留里**带着它自己的 `RSC_EXIT=1`** ⇒ 计数从 **1** 起步 ⇒ **第一拍即报
「TERMINAL MARKER PRESENT」**，而那个标记属于**上一个运行**。
**这是一个「读到了终止标记」的假阳性，且它点的是错的运行**——
与那个运行**是否**结束无关。**两种结局共用一条文本通道**时，第三次复现本库该族缺陷。

### ④ 处置（**断言，而非声称**）

rc4 启动器**不声称**截断成功，而是**验证**：
`: > "$LOG"` → 写 4 行头 → `wc -l` **必须恰为 4**，否则 `exit 4` **且不启动 python**。
实测：`log truncated and header written: 4 lines`；`head -1` = rc4 头；
**`grep -c "RSC_EXIT="` ＝ 0** ⇒ 守卫从**真零**起步。

**★并把「哪个对象产生了本轮读数」写进本轮日志自身的头部**：
`writer sha256: 077cb379…` ＋ cmdline。**不点名的日志无法与本轮的写入器对上。**

### ⑤ 存证

- `logs/53_full_rc2_wtauc_crash_20260924.log`（89 行，sha `502cb3be…`，核过未被改动）
- `logs/53_full_rc3_partial_aborted_20260924.log`（**110 行**）
- **★文件名原写作 `…_98lines_…`，被我改掉了**：首次测得 98，kill 前它已长到 110
  ⇒ **文件名里断言了一个已经过时的计数**。计数属于记录，不属于文件名。

---

## C-176 — 2026-09-24 — C-172 撤回的**载体补齐**：判据到达了结论行与报告，
## 但**产生结论的那一步**、以及两处**范围错标**，是在同侪指出后才补上的

### ① 第一遍漏了什么

C-172 的撤回触及 `_ceiling_check.py`（文档串＋运行时打印）、报告 `16_`（4 处行内标记
＋§9(e)）、两份记忆。**`pipeline_reports/progress.md` 里同一主张出现三次，一处未动**：
`:6055`、`:6168`、**`:6549`（落地时预注册，是其中最会被 grep 到的一条）**——由同侪指出，
我回源逐行核实后确认，第一遍补标（行数 6764 不变，每条仍在原位）。

### ② 第二遍补的是「**产生结论的那一步**」

第一遍标了 `:6055` 的**结论**，却把**推出它的那句话**（`:6054`
「残差为正 ⇒ 对照的分数在箱内不恒定 ⇒ 其 within-t0 AUC 必然 >0.5」）**留在原位无标记**
——**读者读到推理处，看不到警告**。第二遍补 `:6054`；另补 `:6056`
（「这是重跑可以用的一致性判据，此前没有。」——**现为假**）。

### ③ ★并修正我自己的**范围错标**（`:6168`）

第一遍在**块首**打了一个裸的「该判据已撤回」。**块首不是块**：
其下两条分支规则**不随之一同作废**——

- 第 1 条（`within-t0>0.5 ⇒ shuffled_control_at_chance 再次失败 ⇒ 成因在特征/模型通道`）
  **实质仍有效**：修复版写入器里该判据**由 within-t0 列算出**（`:1401-1404`）
  ⇒ 它是**操作指标**，它为 False 是**关于对照的真读数**。
- 第 2 条（`(池化~0.84, within-t0~0.5) ⇒ 写入器缺陷`）**整条作废**（＝C-172 §④ 撤回的预言机），
  已单独在 `:6173` 加标记。

**⇒ 这正是 C-166 的缺陷形态（一次陈述、置于标题下、读作覆盖其下一切），
这次是我自己犯的。** 裸「作废」会让读者**丢掉一条仍然有效的规则**。

### ④ ★同侪给的两处行号**差一**（我在文件上读，不在记忆上读）

同侪报 `:6053` 与 `:6057`；**该文件此两行是空行**。真身在 `:6054` 与 `:6056`。
**⇒ 与我本人上一轮对同侪摘引逐字回收同族**：**引用行号也是引用，也要回源**。
（同侪同一轮自陈其首个检查因 grep 模式 `已证伪|已被证伪` 未覆盖我的
「已被**穷举**证伪」而误判「3 条中 1 条——**差一步就把我做对的事报成没做完**」。）
"""
LEDGER_END = None

raw = io.open(LEDGER, "rb").read()
sha_before = hashlib.sha256(raw).hexdigest()[:16]
text = io.open(LEDGER, encoding="utf-8").read()
assert "C-174" not in text, "C-174 already present"
assert text.endswith("\n"), "unexpected tail"
io.open(LEDGER, "w", encoding="utf-8", newline="").write(text + ENTRY)

after = io.open(LEDGER, "rb").read()
assert after.startswith(raw), "PREFIX CHANGED -- append-only violated"
at = io.open(LEDGER, encoding="utf-8").read()
for tag in ("## C-174", "## C-175", "## C-176"):
    assert tag in at, tag
n = at.count("\n")
print("appended C-174 / C-175 / C-176")
print("  size %d -> %d B  (+%d)" % (len(raw), len(after), len(after) - len(raw)))
print("  lines 6764 -> %d" % n)
print("  sha16 %s -> %s" % (sha_before, hashlib.sha256(after).hexdigest()[:16]))
print("  prefix byte-for-byte preserved: OK")
